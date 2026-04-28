from dataclasses import dataclass

import fitz


@dataclass
class DocumentChunk:
    content: str
    metadata: dict[str, object]


def load(path: str, source_name: str) -> list[DocumentChunk]:
    chunks = []
    with fitz.open(path) as doc:
        total_pages = len(doc)
        for page in doc:
            text = str(page.get_text("text"))
            if not text:
                continue
            chunks.append(
                DocumentChunk(
                    content=text,
                    metadata={
                        "total_pages": total_pages,
                        "source_name": source_name,
                        "page": page.number + 1,
                        "format": "pdf",
                    },
                )
            )
    return chunks
