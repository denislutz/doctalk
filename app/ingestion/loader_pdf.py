from dataclasses import dataclass


@dataclass
class DocumentChunk:
    content: str
    metadata: dict


def load_pdf(path: str) -> list[DocumentChunk]:
    # TODO: implement with PyMuPDF
    raise NotImplementedError
