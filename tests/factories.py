"""
Factory Boy factories for DocTalk domain objects.

Usage:
    from tests.factories import DocRecordFactory, RetrievedChunkFactory

    record = DocRecordFactory()                       # default values
    record = DocRecordFactory(topic="medicine")       # override one field
    records = DocRecordFactory.create_batch(5)        # list of 5

    chunk = RetrievedChunkFactory(content="custom text")

Factories produce plain dataclass / Pydantic instances — they do NOT touch any
database. To persist a DocRecord into a test registry use:

    record = DocRecordFactory()
    doc_id = registry.insert_document(
        topic=record.topic,
        source_name=record.source_name,
        filename=record.filename,
        format=record.format,
        file_hash=factory.Faker("sha256").generate(),
        chunk_count=record.chunk_count,
    )
"""

import factory
from doctalk_shared.models import RetrievedChunk, SourceChunk
from factory import Factory, Faker, LazyAttribute, Sequence

from app.storage.doc_registry import DocRecord


class DocRecordFactory(Factory):
    class Meta:
        model = DocRecord

    doc_id = Faker("uuid4")
    topic = Sequence(lambda n: f"topic_{n}")
    source_name = Faker("file_name", extension="pdf")
    filename = LazyAttribute(lambda o: o.source_name)
    format = factory.Iterator(["pdf", "md", "docx", "txt"])
    chunk_count = Faker("random_int", min=1, max=50)
    ingested_at = Faker("iso8601")


class RetrievedChunkFactory(Factory):
    class Meta:
        model = RetrievedChunk

    content = Faker("paragraph")
    source_name = Faker("file_name", extension="pdf")
    format = factory.Iterator(["pdf", "md", "docx", "txt"])
    page = Faker("random_int", min=1, max=200)
    section_header = Faker("sentence", nb_words=4)
    score = Faker("pyfloat", min_value=0.0, max_value=1.0, right_digits=4)


class SourceChunkFactory(Factory):
    class Meta:
        model = SourceChunk

    source_name = Faker("file_name", extension="pdf")
    format = factory.Iterator(["pdf", "md", "docx", "txt"])
    page_number = Faker("random_int", min=1, max=200)
    section_header = Faker("sentence", nb_words=4)
    content_snippet = Faker("sentence")
    relevance_score = Faker("pyfloat", min_value=0.0, max_value=1.0, right_digits=4)
