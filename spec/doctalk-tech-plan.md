# DocTalk — Technical Specification

**Type:** Self-hosted RAG system  
**Stack:** Python 3.12 · FastAPI · Qdrant · LangChain · Ollama · Streamlit

---

## 1. Project Goal

Build a self-hosted, GDPR-compliant RAG application where companies upload documents (DOCX, PDF, MD, TXT), organize them into topic collections, and query across their data via natural language. No data leaves the company network.

**Target demo scenario:** A compliance officer uploads policy documents, HR guidelines, and plain-text reports into separate collections — then asks questions like "What are our data retention requirements for employee records?" and gets sourced answers.

---

## 2. Architecture Overview

```ascii
┌─────────────────────────────────────────────────────────────┐
│                      DocTalk System                         │
│                                                             │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  Upload   │───▶│  Ingestion   │───▶│   Qdrant         │  │
│  │  API      │    │  Pipeline    │    │   Vector DB      │  │
│  │ (FastAPI) │    │              │    │                  │  │
│  └──────────┘    │ ┌──────────┐ │    │ Collection A     │  │
│                  │ │ Loaders  │ │    │ Collection B     │  │
│  ┌──────────┐   │ │ DOCX     │ │    │ Collection C     │  │
│  │  Query   │   │ │ PDF      │ │    └──────────────────┘  │
│  │  API     │   │ │ MD       │ │             │            │
│  │ (FastAPI)│   │ │ TXT      │ │    ┌────────▼─────────┐  │
│  └────┬─────┘   │ └──────────┘ │    │   Retrieval      │  │
│       │         │ ┌──────────┐ │    │   Chain           │  │
│       │         │ │ Chunker  │ │    │   (LangChain)     │  │
│       └────────▶│ │(adaptive)│ │    │                   │  │
│                 │ └──────────┘ │    │ Hybrid Search     │  │
│  ┌──────────┐  │ ┌──────────┐ │    │ Re-Ranking        │  │
│  │ Streamlit│  │ │ Embedder │ │    │ Source Attribution │  │
│  │ Frontend │  │ │ (local)  │ │    └────────┬──────────┘  │
│  └──────────┘  │ └──────────┘ │             │             │
│                └──────────────┘    ┌────────▼─────────┐   │
│                                    │   LLM            │   │
│                                    │   Ollama(local)   │   │
│                                    │   or Claude API   │   │
│                                    └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Tech Stack

| Layer                | Technology                                       | Why                                                             |
| -------------------- | ------------------------------------------------ | --------------------------------------------------------------- |
| **Language**         | Python 3.12+                                     | All libraries native, async support, PEP 695 type syntax        |
| **API Framework**    | FastAPI + Pydantic                               | Async, typed, auto-docs                                         |
| **Vector DB**        | Qdrant (local binary)                            | Collection isolation, metadata filtering, sparse vector support |
| **Embeddings**       | `sentence-transformers/all-MiniLM-L6-v2` (local) | Free, fast, GDPR-compliant                                      |
| **RAG Framework**    | LangChain                                        | LCEL chains, prompt templates, output parsers                   |
| **LLM**              | Ollama (local) + Claude API toggle               | Self-hosted default, API option for quality comparison          |
| **Doc Processing**   | `python-docx`, `PyMuPDF`, `markdown`             | One loader per format, all pure Python                          |
| **Frontend**         | Streamlit (MVP)                                  | Fast to build, good enough for demo                             |
| **Containerization** | Docker Compose                                   | Production deployment only                                      |
| **Evaluation**       | RAGAS + DeepEval                                 | Pipeline quality metrics                                        |
| **Testing**          | pytest + httpx (async) + factory-boy             | Standard Python testing with DB factory fixtures                |

---

## 4. Data Model

### Qdrant Collection Strategy

One Qdrant collection per topic. Each collection stores chunks with rich metadata.

```python
# Collection naming
collection_name = f"doctalk_{tenant}_{topic_slug}"
# Example: "doctalk_default_hr_policies"

# Point payload (metadata per chunk)
{
    "doc_id": "uuid",
    "filename": "employee_handbook.pdf",
    "format": "pdf",
    "topic": "hr_policies",
    "chunk_index": 3,
    "total_chunks": 42,
    "page_number": 5,
    "section_header": "3.1 Leave Policy",
    "ingested_at": "2026-04-15T10:30:00Z",
    "content_preview": "First 100 chars..."
}
```

### Shared Library (`shared/doctalk_shared/models.py`)

All Pydantic models live in a shared package imported by both the API and the Streamlit frontend.

```python
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class QueryRequest(BaseModel):
    question: str
    topics: list[str] | None = None
    top_k: int = 5
    use_reranking: bool = True
    history: list[ChatMessage] = []

class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    tokens_used: int
    retrieval_time_ms: float
    generation_time_ms: float

class CollectionInfo(BaseModel):
    name: str
    description: str
    size: int
    formats: list[str] = []
    doc_count: int = 0
    documents: list[IndexedDocument] = []
    metadata: dict[str, object] = {}
```

---

## 5. Document Ingestion Pipeline

### 5.1 Format-Specific Loaders

| Format   | Library                      | Chunking Strategy                                      | Metadata Extracted                        |
| -------- | ---------------------------- | ------------------------------------------------------ | ----------------------------------------- |
| **PDF**  | `PyMuPDF` (fitz)             | Split by pages → paragraphs within page                | page_number, total_pages                  |
| **DOCX** | `python-docx`                | Split by heading hierarchy (H1→H2→H3)                  | section_header, heading_level, style_name |
| **MD**   | regex                        | Split by `##` heading markers. Code blocks kept intact | section_header, heading_level, has_code   |
| **TXT**  | built-in                     | Whole file → token-based chunker at 512 tokens         | format                                    |
| **EPUB** | `ebooklib` + `BeautifulSoup` | Chapter/heading boundaries                             | section_header, heading_level             |

### 5.2 Chunking

Two-pass approach:

1. Loader splits on semantic boundaries (pages, headings) → `DocumentChunk`
2. `chunker.py` applies 512-token window with 50-token overlap on anything too large

Config: max 512 tokens, 50-token overlap, minimum 50 tokens. Token counts via `tiktoken` (`cl100k_base`).

### 5.3 Embedding & Storage

Embedded locally with `all-MiniLM-L6-v2` (384 dimensions). Each chunk upserted to Qdrant with UUID id and metadata payload.

---

## 6. RAG Query Pipeline

### 6.1 Search Types

Three mechanisms — dense semantic search, sparse keyword search, and cross-encoder re-ranking — are combined for best results. For a full explanation of how each works, how chunks are stored, dot product scoring, RRF merging, and why they complement each other, see [search-concepts.md](search-concepts.md).

**Index-time requirement:** each chunk must be upserted with both a `dense` vector (384 floats) and a `sparse` vector (hash-based TF weights). The Qdrant collection must be created with both vector configs declared (`VectorParams` + `SparseVectorParams`). See `vector_db_client.py` and `embedder.py`.

### 6.2 Retrieval Flow

```text
User Question
        │
        ├─▶ Dense Search  (search_collection_dense)                      ✅
        │       embedder.embed_dense([question]) → vector [384 floats]
        │       Qdrant cosine similarity
        │       → list[RetrievedChunk]  top_k=20, by cosine score
        │
        ├─▶ Sparse / BM25 Search  (search_collection_sparse)             ✅
        │       question → sparse vector {term: weight}
        │       Qdrant sparse search
        │       → list[RetrievedChunk]  top_k=20, by BM25 score
        │
        ├─▶ Reciprocal Rank Fusion  (reciprocal_rank_fusion)        ✅
        │       score = 1/(60 + rank_dense) + 1/(60 + rank_bm25)
        │       → list[RetrievedChunk]  top_k=10, by RRF score
        │
        ├─▶ Cross-Encoder Re-Ranking  (reranker.rerank)             ✅
        │       CrossEncoder.predict([(question, chunk.content), ...])
        │       → list[RetrievedChunk]  top_k=5, by relevance score
        │
        └─▶ LLM Generation  (chain.generate_answer)                 ✅
                LCEL: ChatPromptTemplate | ChatOllama | StrOutputParser
                → str  answer with [Source: filename, page] citations
```

### 6.3 Generation Prompt

System prompt instructs the model to answer only from provided context chunks, cite sources as `[Source: filename, page/section]`, and return "I couldn't find this in the indexed documents." when context is insufficient.

### 6.4 Conversation Memory

History carried as `list[ChatMessage]` in `QueryRequest.history` (oldest first), injected into the chain via `MessagesPlaceholder`.

---

## 7. API Endpoints

```text
POST   /collections                    Create topic collection
GET    /collections                    List all collections
GET    /collections/{topic}            Collection stats & doc list
DELETE /collections/{topic}            Delete collection + all data

POST   /collections/{topic}/upload     Upload document (multipart)
DELETE /collections/{topic}/docs/{id}  Remove single document

POST   /query                          Ask a question
GET    /query/history                  Recent queries (session-based)

GET    /health                         System health (Qdrant, Ollama, embeddings)
```

---

## 8. Project Structure

```text
doctalk/
├── docker-compose.yml          # Production deployment
├── Dockerfile
├── pyproject.toml
├── .env.example
├── README.md
│
├── shared/
│   └── doctalk_shared/
│       └── models.py           # All Pydantic models
│
├── app/
│   ├── main.py                 # FastAPI app, lifespan
│   ├── config.py               # pydantic-settings
│   │
│   ├── api/
│   │   ├── collections.py
│   │   ├── upload.py
│   │   ├── query.py
│   │   └── health.py
│   │
│   ├── ingestion/
│   │   ├── file_loader_service.py
│   │   ├── chunker.py
│   │   └── embedder.py
│   │
│   ├── retrieval/
│   │   ├── search_service.py   # Dense + BM25 + RRF
│   │   ├── reranker.py         # Cross-encoder
│   │   └── chain.py            # LangChain LCEL chain
│   │
│   └── storage/
│       ├── vector_db_client.py
│       └── doc_registry.py     # SQLite doc registry
│
├── eval/
│   ├── test_dataset.json
│   ├── run_ragas.py
│   └── run_deepeval.py
│
├── tests/
│   ├── test_loaders.py
│   ├── test_chunker.py
│   ├── test_api.py
│   └── test_retrieval.py
│
└── scripts/
    ├── seed_demo.py
    └── benchmark.py
```

---

## 9. Phased Build Status

### Phase 1: Ingestion Pipeline ✅

| Task                                                   | Done |
| ------------------------------------------------------ | ---- |
| Project setup (uv, FastAPI skeleton, Docker Compose)   | ✅    |
| Qdrant client wrapper (create/list/delete collections) | ✅    |
| PDF loader + tests                                     | ✅    |
| DOCX loader + tests                                    | ✅    |
| MD loader + tests                                      | ✅    |
| TXT loader + tests                                     | ✅    |
| Adaptive chunker (token-based, format-aware)           | ✅    |
| Embedder + Qdrant upsert                               | ✅    |
| Upload API endpoint                                    | ✅    |
| Doc Registry (SQLite duplicate guard + doc list)       | ✅    |
| EPUB loader (bonus)                                    | ✅    |

### Phase 2: Query Engine ✅

| Task                                                      | Done |
| --------------------------------------------------------- | ---- |
| LangChain QA chain (LCEL, prompt template, output parser) | ✅    |
| Conversation memory (history via MessagesPlaceholder)     | ✅    |
| Dense search wired into pipeline                          | ✅    |
| Cross-encoder re-ranker                                   | ✅    |
| Query API endpoint                                        | ✅    |
| BM25 / sparse search                                      | ✅    |
| Reciprocal Rank Fusion merge                              | ✅    |

### Phase 3: UI ✅

| Task                                    | Done |
| --------------------------------------- | ---- |
| Streamlit frontend — upload page        | ✅    |
| Streamlit frontend — chat page          | ✅    |
| Streamlit frontend — collection manager | ✅    |
| Collection stats endpoint               | ✅    |

### Phase 4: AI/Evaluation (next — priority) ← **current focus**

AI-first topics: provider flexibility, evaluation frameworks, observability. These are the highest learning-value items for portfolio positioning.

| Task                                   | Done |
| -------------------------------------- | ---- |
| Test Q&A dataset (20+ pairs)           | ❌    |
| RAGAS evaluation                       | ❌    |
| DeepEval integration                   | ❌    |
| Benchmark script                       | ❌    |
| Claude API provider toggle             | ❌    |
| Structured logging (per-request trace) | ❌    |

### Phase 5: Code Style — OOP vs Functional (deferred)

Evaluate which classes justify being classes and which should be plain functions. The key question is whether the object holds expensive-to-initialize state (model weights, DB connections) that must be reused across calls — if yes, the class is justified. If the "class" is just a namespace for one or two stateless functions, convert to module-level functions.

| Class              | Holds shared state?                               | Verdict                                                              | Done |
| ------------------ | ------------------------------------------------- | -------------------------------------------------------------------- | ---- |
| `Reranker`         | Yes — `CrossEncoder` model loaded once at startup | Keep as class; loading per-call would add ~1–2s latency every query  | ❌    |
| `Embedder`         | Yes — `SentenceTransformer` + sparse model        | Keep as class for same reason                                        | ❌    |
| `VectorDB`         | Yes — Qdrant client + connection                  | Keep as class                                                        | ❌    |
| `DocRegistry`      | Yes — SQLite connection                           | Keep as class                                                        | ❌    |
| `IngestionService` | No own state — wraps injected collaborators       | Consider converting to module-level functions                        | ❌    |
| `search_service`   | Already module-level functions                    | ✅ Already functional                                                | ✅    |
| `chain.py`         | Already module-level functions                    | ✅ Already functional                                                | ✅    |

**Rule of thumb:** a class is justified when construction cost (model load, connection open) must be paid once and the instance reused. A single-method class with no expensive constructor is just a function with extra syntax.

---

### Phase 6: Hardening + Polish (deferred)

Infrastructure and presentation work — do after evaluation is solid.

| Task                                   | Done |
| -------------------------------------- | ---- |
| Python 3.12 upgrade                    | ❌    |
| Document delete endpoint               | ❌    |
| API key auth middleware                | ❌    |
| Sample data seeding script             | ❌    |
| Docker optimization                    | ❌    |
| README with screenshots                | ❌    |

#### Python 3.12 Upgrade

**Goal:** Adopt PEP 695 type syntax (`type`, `[T]` generics) across the codebase for cleaner, more expressive type annotations.

**Why PEP 695 matters for this project:**

| Feature | Old way (3.11) | New way (3.12) |
| --- | --- | --- |
| Type alias | `Sample: TypeAlias = dict[str, object]` | `type Sample = dict[str, object]` |
| Generic function | `def first(xs: list[T]) -> T` + `TypeVar("T")` | `def first[T](xs: list[T]) -> T` |
| Generic class | `class Stack(Generic[T])` + `TypeVar("T")` | `class Stack[T]` |
| Recursive alias | Impossible without `from __future__` | `type Tree[T] = T \| list[Tree[T]]` |

PEP 695 aliases are **lazily evaluated** (right-hand side not resolved at import time), which eliminates forward-reference `"string"` hacks and makes recursive types possible without `from __future__ import annotations`.

**Migration steps:**

1. **Install Python 3.12**

   ```bash
   uv python install 3.12
   ```

2. **Update `pyproject.toml`**

   ```toml
   requires-python = "==3.12.*"
   ```

   And in `[tool.mypy]`:

   ```toml
   python_version = "3.12"
   ```

3. **Re-pin the lockfile**

   ```bash
   uv sync
   ```

4. **Migrate type aliases** — search for `TypeAlias` imports and plain assignments used as aliases:

   ```python
   # before
   from typing import TypeAlias
   Sample: TypeAlias = dict[str, object]

   # after
   type Sample = dict[str, object]
   ```

5. **Migrate generic functions** — replace `TypeVar` boilerplate:

   ```python
   # before
   T = TypeVar("T")
   def first(xs: list[T]) -> T: ...

   # after
   def first[T](xs: list[T]) -> T: ...
   ```

6. **Migrate generic classes** — replace `Generic[T]` base:

   ```python
   # before
   class Repository(Generic[T]): ...

   # after
   class Repository[T]: ...
   ```

7. **Run typecheck and tests** to confirm no regressions:

   ```bash
   mise run dev-check
   ```

**Files most likely to change:** `eval/run_ragas.py`, `shared/doctalk_shared/models.py`, any utility with `TypeVar`.

---

## 10. Auto Metadata Extraction

### Goal

On file upload, automatically infer the document title and author to prefill the "Source Name" field. Cascading fallback: embedded metadata → LLM extraction → filename.

### Strategy

```text
1. Embedded metadata (PDF: fitz.metadata, DOCX: core_properties)
   → valid & non-junk?  return (source: "file_metadata", confidence: "high")

2. LLM extraction on first ~2 pages via Ollama (format="json")
   → got a title?  return (source: "llm", confidence: per model)

3. Filename fallback
   → return (source: "filename", confidence: "low")
```

Junk filter: reject titles matching `Microsoft Word - *`, `Untitled*`, filenames with extensions, strings < 3 chars.

### Endpoint

```text
POST /extract-metadata   (stateless — does not store anything)
```

### source_name Construction

| Title | Author | Stored `source_name`   |
| ----- | ------ | ---------------------- |
| ✓     | ✓      | `"{title} — {author}"` |
| ✓     | ✗      | `"{title}"`            |
| ✗     | —      | filename               |

---

## 11. Integration Testing Infrastructure

> **Status: not started** — set up before Phase 4 evaluation work begins.

### Overview

Deep integration tests that hit real services (SQLite doc registry, Qdrant) with deterministic, factory-generated data — no mocks.

### Stack

| Tool            | Role                                                         |
| --------------- | ------------------------------------------------------------ |
| `pytest`        | Test runner, fixture system                                  |
| `factory-boy`   | SQLAlchemy model factories (equivalent to Ruby's FactoryBot) |
| `httpx`         | Async FastAPI test client                                    |
| Qdrant (local)  | Real vector DB — test collections created/torn down per run  |
| SQLite (in-mem) | Real doc registry — rolled back after each test              |

### Structure

```text
tests/
├── conftest.py          # db session fixture, factory session wiring, Qdrant test client
├── factories.py         # DocumentFactory, CollectionFactory, ChunkFactory
├── test_loaders.py      # existing
├── test_chunker.py      # existing
├── test_api.py          # existing
├── test_retrieval.py    # existing
└── test_registry.py     # new — doc registry integration tests
```

### Key Patterns

- Each test gets a fresh SQLite session, rolled back on teardown
- Qdrant test collections are prefixed `test_` and deleted after the test
- `factory-boy` `SubFactory` handles relationships (e.g. chunks belonging to a document)
- `build()` for in-memory objects, `create()` to persist to DB

---

## 12. Future Extensions

- **Agentic layer:** LangGraph agent for autonomous multi-step retrieval
- **Multi-tenant isolation:** Per-company API keys with collection-level access control
- **Web scraping loader:** URL ingestion alongside file upload
- **React frontend:** Replace Streamlit
- **Azure deployment:** ACI/ACA for ComplianceCoder demo

---

## 12. Success Criteria

| Metric                                   | Target                                |
| ---------------------------------------- | ------------------------------------- |
| Supports 4 document formats              | PDF, DOCX, MD, TXT all working        |
| RAG answer accuracy (RAGAS faithfulness) | > 0.80                                |
| RAG context relevancy (RAGAS)            | > 0.75                                |
| Query response time (local, Ollama)      | < 5 seconds                           |
| Query response time (Claude API)         | < 3 seconds                           |
| Docker Compose single-command startup    | `docker compose up` → everything runs |
| API documentation                        | Auto-generated Swagger at `/docs`     |
| Test coverage                            | > 70% (loaders + API)                 |
| GitHub README with demo GIF              | Portfolio-ready                       |
