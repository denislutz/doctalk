import tiktoken

from .loader_pdf import DocumentChunk

ENCODING = tiktoken.get_encoding("cl100k_base")
MAX_TOKENS = 512
OVERLAP = 50
MIN_TOKENS = 50


def chunk(documents: list[DocumentChunk]) -> list[DocumentChunk]:
    result = []
    for doc in documents:
        tokens = ENCODING.encode(doc.content)
        if len(tokens) <= MAX_TOKENS:
            result.append(doc)
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
                    metadata=doc.metadata,
                )
            )
            start += MAX_TOKENS - OVERLAP
    return result
