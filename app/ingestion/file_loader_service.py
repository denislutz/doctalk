import re
from dataclasses import dataclass
from typing import NotRequired, TypedDict

import fitz
import tiktoken

ENCODING = tiktoken.get_encoding("cl100k_base")
MAX_TOKENS = 512
OVERLAP = 50
MIN_TOKENS = 50
HEADER_RE = re.compile(r"^(#+)\s+(.+)$")


class Metadata(TypedDict):
    source_name: str
    format: str
    page: NotRequired[int]
    section_header: NotRequired[str | None]
    heading_level: NotRequired[int]
    has_code: NotRequired[bool]


@dataclass
class DocumentChunk:
    content: str
    metadata: Metadata


def normalize_chunks(full_chunks: list[DocumentChunk]) -> list[DocumentChunk]:
    result = []
    for chunk in full_chunks:
        tokens = ENCODING.encode(chunk.content)
        if len(tokens) <= MAX_TOKENS:
            result.append(chunk)
            continue

        start = 0
        while start < len(tokens):
            end = min(start + MAX_TOKENS, len(tokens))
            window = tokens[start:end]
            if len(window) < MIN_TOKENS:
                break
            result.append(
                DocumentChunk(
                    content=ENCODING.decode(window),
                    metadata=chunk.metadata,
                )
            )
            start += MAX_TOKENS - OVERLAP
    return result


def load_pdf(path: str, source_name: str) -> list[DocumentChunk]:
    full_chunks = []
    with fitz.open(path) as doc:
        for page in doc:
            text = str(page.get_text("text"))
            if not text:
                continue
            full_chunks.append(
                DocumentChunk(
                    content=text,
                    metadata={
                        "source_name": source_name,
                        "format": "pdf",
                        "page": page.number or 0 + 1,
                    },
                )
            )
    return normalize_chunks(full_chunks)


def load_docx(path: str, source_name: str) -> list[DocumentChunk]:
    from docx import Document

    doc = Document(path)
    full_chunks: list[DocumentChunk] = []
    current_header: str | None = None
    current_level: int = 0
    buffer: list[str] = []

    def flush() -> None:
        text = "\n".join(buffer).strip()
        if text:
            full_chunks.append(
                DocumentChunk(
                    content=text,
                    metadata={
                        "source_name": source_name,
                        "format": "docx",
                        "section_header": current_header,
                        "heading_level": current_level,
                    },
                )
            )
        buffer.clear()

    for par in doc.paragraphs:
        style_name = par.style.name if par.style else ""
        if style_name and style_name.startswith("Heading"):
            flush()
            try:
                current_level = int(style_name.split()[-1])
            except ValueError:
                current_level = 0
            current_header = par.text
        else:
            if par.text.strip():
                buffer.append(par.text)

    flush()

    return normalize_chunks(full_chunks)


def load_md(path: str, source_name: str) -> list[DocumentChunk]:
    # read md line by line
    # if line starts with #, it's a header
    # if line starts with ```, it's a code block
    # if line is empty, it's a separator
    # if line is not empty, it's a paragraph

    full_chunks: list[DocumentChunk] = []
    buffer: list[str] = []
    current_header: str | None = None
    current_level: int = 0
    in_code_fence: bool = False

    def flush() -> None:
        text = "\n".join(buffer).strip()
        if text:
            full_chunks.append(
                DocumentChunk(
                    content=text,
                    metadata={
                        "source_name": source_name,
                        "format": "md",
                        "section_header": current_header,
                        "heading_level": current_level,
                        "has_code": in_code_fence,
                    },
                )
            )
        buffer.clear()

    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
        for line in lines:
            code_fence = line.startswith("```")
            if code_fence:
                in_code_fence = not in_code_fence
                buffer.append(line)
                continue

            if not in_code_fence:
                m = HEADER_RE.match(line)
                if m:
                    flush()
                    current_level = len(m.group(1))
                    current_header = m.group(2)
                    continue

            buffer.append(line)

    flush()
    return normalize_chunks(full_chunks)


def load_epub(path: str, source_name: str) -> list[DocumentChunk]:
    import ebooklib
    from bs4 import BeautifulSoup
    from ebooklib import epub

    book = epub.read_epub(path)
    full_chunks: list[DocumentChunk] = []

    for item in book.get_items():
        if item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        soup = BeautifulSoup(item.get_content(), "html.parser")
        heading_tag = soup.find(re.compile(r"^h[1-6]$"))
        section_header: str | None = heading_tag.get_text(strip=True) if heading_tag else None
        heading_level: int = int(heading_tag.name[1]) if heading_tag else 0
        text = soup.get_text(separator="\n").strip()
        if not text:
            continue
        full_chunks.append(
            DocumentChunk(
                content=text,
                metadata={
                    "source_name": source_name,
                    "format": "epub",
                    "section_header": section_header,
                    "heading_level": heading_level,
                },
            )
        )

    return normalize_chunks(full_chunks)


def load_txt(path: str, source_name: str) -> list[DocumentChunk]:
    # TXT has no inherent structure, so one file → one DocumentChunk.
    # normalize_chunks() handles splitting if it exceeds MAX_TOKENS (512),
    # so the loader just reads the raw text.
    result = []
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
        if not text:
            return []
        result.append(
            DocumentChunk(content=text, metadata={"source_name": source_name, "format": "txt"})
        )
    return result
