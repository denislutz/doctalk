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
from uuid import uuid4


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
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id      TEXT PRIMARY KEY,
                    topic       TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    filename    TEXT NOT NULL,
                    format      TEXT NOT NULL,
                    file_hash   TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    ingested_at TEXT NOT NULL,
                    UNIQUE(file_hash, topic)
                )
            """)
            conn.commit()

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
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE file_hash = ? AND topic = ?",
                (file_hash, topic),
            ).fetchone()
            return int(row[0]) > 0

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def insert_document(
        self,
        *,
        topic: str,
        source_name: str,
        filename: str,
        format: str,
        file_hash: str,
        chunk_count: int,
    ) -> str:
        doc_id = str(uuid4())
        ingested_at = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO documents
                   (doc_id, topic, source_name, filename, format, file_hash, chunk_count, ingested_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, topic, source_name, filename, format, file_hash, chunk_count, ingested_at),
            )
            conn.commit()
        return doc_id

    def delete_document(self, doc_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
            conn.commit()

    def delete_topic(self, topic: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM documents WHERE topic = ?", (topic,))
            conn.commit()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def list_documents(self, topic: str) -> list[DocRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE topic = ? ORDER BY ingested_at DESC", (topic,)
            )
            return [
                DocRecord(
                    doc_id=row["doc_id"],
                    topic=row["topic"],
                    source_name=row["source_name"],
                    filename=row["filename"],
                    format=row["format"],
                    chunk_count=row["chunk_count"],
                    ingested_at=row["ingested_at"],
                )
                for row in rows
            ]

    def ping(self) -> None:
        with self._connect() as conn:
            conn.execute("SELECT 1")

    def get_document(self, doc_id: str) -> DocRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE doc_id = ?",
                (doc_id,),
            ).fetchone()
            if row is None:
                return None
            return DocRecord(
                doc_id=row["doc_id"],
                topic=row["topic"],
                source_name=row["source_name"],
                filename=row["filename"],
                format=row["format"],
                chunk_count=row["chunk_count"],
                ingested_at=row["ingested_at"],
            )
