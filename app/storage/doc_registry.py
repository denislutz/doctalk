"""
Document registry — SQLite-backed table that tracks which documents have been
indexed into which topic collection.

Schema (single table):
    doc_id       TEXT PRIMARY KEY   — UUID generated at upload time
    topic        TEXT NOT NULL      — Qdrant collection name
    source_name  TEXT NOT NULL      — human-readable title / filename
    filename     TEXT NOT NULL      — original upload filename
    format       TEXT NOT NULL      — pdf | docx | md | csv
    file_hash    TEXT NOT NULL      — SHA-256 of raw file bytes (duplicate guard)
    chunk_count  INTEGER NOT NULL
    ingested_at  TEXT NOT NULL      — ISO-8601 UTC timestamp

Uniqueness constraint: (file_hash, topic) — same file can live in different topics
but cannot be indexed twice into the same topic.
"""

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class DocRecord:
    doc_id: str
    topic: str
    source_name: str
    filename: str
    format: str
    chunk_count: int
    ingested_at: str


class DocRegistry:
    def __init__(self, db_path: str | Path) -> None:
        # db_path is the filesystem path to the SQLite file, e.g. /app/data/registry.db
        # Calling code (main.py lifespan) should pass settings.registry_db_path here.
        self._db_path = str(db_path)
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        # Open a new connection; callers are responsible for closing it.
        # Use check_same_thread=False because FastAPI may call from different threads.
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        # Create the documents table if it doesn't exist yet.
        # Run once at startup — safe to call repeatedly (IF NOT EXISTS guard).
        # TODO: execute CREATE TABLE IF NOT EXISTS with the schema described in the module docstring.
        #       Add a UNIQUE constraint on (file_hash, topic) so the DB itself enforces deduplication.
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Duplicate detection
    # ------------------------------------------------------------------

    @staticmethod
    def compute_hash(file_bytes: bytes) -> str:
        # Return the hex SHA-256 digest of raw file bytes.
        # Call this before insert_document to get the hash to check/store.
        return hashlib.sha256(file_bytes).hexdigest()

    def is_duplicate(self, file_hash: str, topic: str) -> bool:
        # Return True if a row with (file_hash, topic) already exists in the table.
        # Used by the upload endpoint to reject re-indexing the same file into the same topic.
        # TODO: SELECT COUNT(*) FROM documents WHERE file_hash = ? AND topic = ?
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def insert_document(
        self,
        *,
        doc_id: str,
        topic: str,
        source_name: str,
        filename: str,
        format: str,
        file_hash: str,
        chunk_count: int,
    ) -> None:
        # Insert a new document record after successful Qdrant upsert.
        # ingested_at should be set to datetime.now(UTC).isoformat() here.
        # Raise sqlite3.IntegrityError (or a custom DuplicateDocumentError) if the
        # UNIQUE(file_hash, topic) constraint fires — caller can catch and return HTTP 409.
        # TODO: INSERT INTO documents (...) VALUES (...)
        raise NotImplementedError

    def delete_document(self, doc_id: str) -> None:
        # Remove a single document record by doc_id.
        # Called after the corresponding Qdrant points are deleted (see vector_db_client).
        # TODO: DELETE FROM documents WHERE doc_id = ?
        raise NotImplementedError

    def delete_topic(self, topic: str) -> None:
        # Remove ALL document records for a topic.
        # Called when the entire Qdrant collection is deleted.
        # TODO: DELETE FROM documents WHERE topic = ?
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def list_documents(self, topic: str) -> list[DocRecord]:
        # Return all documents indexed into a topic, ordered by ingested_at DESC.
        # Used by GET /collections/{topic} to show the indexed source list.
        # TODO: SELECT * FROM documents WHERE topic = ? ORDER BY ingested_at DESC
        #       Map each sqlite3.Row to a DocRecord dataclass and return the list.
        raise NotImplementedError

    def get_document(self, doc_id: str) -> DocRecord | None:
        # Return a single DocRecord by doc_id, or None if not found.
        # Useful for existence checks before delete operations.
        # TODO: SELECT * FROM documents WHERE doc_id = ?
        raise NotImplementedError
