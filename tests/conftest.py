"""
Test environment fixtures — Rails-style database lifecycle management.

Fixture scopes:
  session  — vector_db_client, settings_test  (one Qdrant connection for the whole run)
  function — registry, vector_db_collection   (fresh SQLite + clean collection per test)

Cleanup contract:
  - SQLite: :memory: databases are destroyed automatically when the connection closes.
  - Qdrant: each test that needs a collection requests `vector_db_collection(name)` which
    creates the collection before the test and deletes it after, regardless of outcome.
"""

import os

import pytest
from fastapi.testclient import TestClient

# Load .env.test before app/config.py is imported so Settings picks up test values.
# pytest-env handles this automatically via [tool.pytest.ini_options] env_files entry,
# but we also do it here as a belt-and-suspenders guard for direct pytest invocations.
os.environ.setdefault("VECTOR_DB_URL", "http://localhost:6335")
os.environ.setdefault("REGISTRY_DB_PATH", ":memory:")
os.environ.setdefault("ENVIRONMENT", "testing")

from app.config import Settings  # noqa: E402
from app.storage.doc_registry import DocRegistry  # noqa: E402
from app.storage.vector_db_client import VectorDB  # noqa: E402

# ---------------------------------------------------------------------------
# Session-scoped: one connection to the test Qdrant for the whole run
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return Settings(
        environment="testing",
        vector_db_url=os.environ["VECTOR_DB_URL"],
        registry_db_path=":memory:",
        api_key="test-key",
        log_level="WARNING",
    )


@pytest.fixture(scope="session")
def vector_db(test_settings: Settings) -> VectorDB:
    return VectorDB(url=test_settings.vector_db_url)


# ---------------------------------------------------------------------------
# Function-scoped: fresh in-memory SQLite registry per test
# ---------------------------------------------------------------------------


@pytest.fixture()
def registry() -> DocRegistry:
    # :memory: gives each fixture call a brand-new empty database.
    return DocRegistry(db_path=":memory:")


# ---------------------------------------------------------------------------
# Collection factory fixture: creates a Qdrant collection, tears it down after.
# Usage: collection_name = test_collection("my_topic")
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_collection(vector_db: VectorDB):
    """
    Returns a factory that creates a named Qdrant collection and schedules cleanup.

    Usage inside a test:
        def test_search(test_collection):
            col = test_collection("my_topic")
            # col is ready to use; deleted when the test ends
    """
    created: list[str] = []

    def _factory(name: str, vector_size: int = 384) -> str:
        vector_db.ensure_collection(name, vector_size=vector_size)
        created.append(name)
        return name

    yield _factory

    for name in created:
        vector_db.delete_collection(name)


# ---------------------------------------------------------------------------
# FastAPI test client (optional — import only when testing the HTTP layer)
# ---------------------------------------------------------------------------


@pytest.fixture()
def api_client(test_settings: Settings):
    # Import here so tests that don't need HTTP don't pay the startup cost.
    from app.main import app

    with TestClient(app) as client:
        yield client
