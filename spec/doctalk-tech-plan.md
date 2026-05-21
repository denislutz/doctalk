# DocTalk — Technical Specification

**Type:** Self-hosted RAG system  
**Stack:** Python 3.12 · FastAPI · Qdrant · LangChain · Ollama · DeepSeek API · Streamlit · React/Next.js

---

## 1. Project Goal

Build a self-hosted, GDPR-compliant RAG application where companies upload documents (DOCX, PDF, MD, TXT), organize them into topic collections, and query across their data via natural language. No data leaves the company network.

**Target demo scenario:** A compliance officer uploads policy documents, HR guidelines, and plain-text reports into separate collections — then asks questions like "What are our data retention requirements for employee records?" and gets sourced answers.

**Portfolio signal:** DocTalk demonstrates the full React/Python/AI stack — FastAPI backend, production-grade hybrid RAG pipeline, and two frontends (Streamlit for rapid prototyping, React/Next.js for production UI). Both frontends consume the same API, showing architectural separation of concerns.

---

## 2. Architecture Overview

```ascii
┌─────────────────────────────────────────────────────────────────┐
│                        DocTalk System                           │
│                                                                 │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────────┐ │
│  │  Upload API  │──▶│  Ingestion   │──▶│   Qdrant             │ │
│  │  (FastAPI)   │   │  Pipeline    │   │   Vector DB          │ │
│  └─────────────┘   │              │   │                      │ │
│                    │ ┌──────────┐ │   │ Collection A         │ │
│  ┌─────────────┐   │ │ Loaders  │ │   │ Collection B         │ │
│  │  Query API   │   │ │ DOCX     │ │   │ Collection C         │ │
│  │  (FastAPI)   │   │ │ PDF      │ │   └──────────────────────┘ │
│  └──────┬──────┘   │ │ MD / TXT │ │              │             │
│         │          │ └──────────┘ │   ┌───────────▼──────────┐ │
│         │          │ ┌──────────┐ │   │   Retrieval Chain    │ │
│         │          │ │ Chunker  │ │   │   (LangChain)        │ │
│         └─────────▶│ │(adaptive)│ │   │                      │ │
│                    │ └──────────┘ │   │ Dense + BM25 + RRF   │ │
│  ┌─────────────┐   │ ┌──────────┐ │   │ Cross-Encoder Rerank │ │
│  │  Streamlit  │   │ │ Embedder │ │   │ Source Attribution   │ │
│  │  Frontend   │   │ └──────────┘ │   └───────────┬──────────┘ │
│  └─────────────┘   └─────────────┘               │             │
│                                        ┌──────────▼──────────┐ │
│  ┌─────────────┐                       │   LLM Provider      │ │
│  │  React/     │                       │   Ollama (local)    │ │
│  │  Next.js    │                       │   DeepSeek API      │ │
│  │  Frontend   │                       │   (pluggable)       │ │
│  └─────────────┘                       └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

Both frontends consume the same FastAPI endpoints. Streamlit stays as the rapid-demo layer; React is the production-quality portfolio showcase.

---

## 3. Tech Stack

| Layer                | Technology                                       | Why                                                             |
| -------------------- | ------------------------------------------------ | --------------------------------------------------------------- |
| **Language**         | Python 3.12+                                     | All libraries native, async support, PEP 695 type syntax        |
| **API Framework**    | FastAPI + Pydantic                               | Async, typed, auto-docs, SSE streaming                          |
| **Vector DB**        | Qdrant (local binary)                            | Collection isolation, metadata filtering, sparse vector support |
| **Embeddings**       | `sentence-transformers/all-MiniLM-L6-v2` (local) | Free, fast, GDPR-compliant                                      |
| **RAG Framework**    | LangChain                                        | LCEL chains, prompt templates, output parsers                   |
| **LLM**              | Ollama (local) + DeepSeek API                    | Self-hosted default; DeepSeek as cheap remote API example       |
| **Doc Processing**   | `python-docx`, `PyMuPDF`, `markdown`             | One loader per format, all pure Python                          |
| **Frontend A**       | Streamlit (MVP / demo layer)                     | Fast to build, good for rapid demos and internal use            |
| **Frontend B**       | React + Next.js + Tailwind CSS                   | Production UI, streaming chat, portfolio showcase               |
| **Containerization** | Docker Compose                                   | Single-command startup for both frontends + backend             |
| **Evaluation**       | RAGAS + DeepEval                                 | Pipeline quality metrics                                        |
| **Testing**          | pytest + httpx (async) + factory-boy             | Integration tests hitting real services, no mocks               |

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

All Pydantic models live in a shared package imported by the FastAPI app, the Streamlit frontend, and available as a typed contract for the React frontend via the auto-generated OpenAPI schema.

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
        ├─▶ Dense Search  (search_collection_dense)
        │       embedder.embed_dense([question]) → vector [384 floats]
        │       Qdrant cosine similarity
        │       → list[RetrievedChunk]  top_k=20, by cosine score
        │
        ├─▶ Sparse / BM25 Search  (search_collection_sparse)
        │       question → sparse vector {term: weight}
        │       Qdrant sparse search
        │       → list[RetrievedChunk]  top_k=20, by BM25 score
        │
        ├─▶ Reciprocal Rank Fusion  (reciprocal_rank_fusion)
        │       score = 1/(60 + rank_dense) + 1/(60 + rank_bm25)
        │       → list[RetrievedChunk]  top_k=10, by RRF score
        │
        ├─▶ Cross-Encoder Re-Ranking  (reranker.rerank)
        │       CrossEncoder.predict([(question, chunk.content), ...])
        │       → list[RetrievedChunk]  top_k=5, by relevance score
        │
        └─▶ LLM Generation  (chain.generate_answer)
                LCEL: ChatPromptTemplate | BaseChatModel | StrOutputParser
                BaseChatModel = ChatOllama (local) or ChatOpenAI→DeepSeek (remote)
                → str  answer with [Source: filename, page] citations
```

### 6.3 Generation Prompt

System prompt instructs the model to answer only from provided context chunks, cite sources as `[Source: filename, page/section]`, and return "I couldn't find this in the indexed documents." when context is insufficient.

### 6.4 Conversation Memory

History carried as `list[ChatMessage]` in `QueryRequest.history` (oldest first), injected into the chain via `MessagesPlaceholder`.

### 6.5 Streaming

FastAPI exposes a `GET /query/stream` endpoint using `StreamingResponse` with `text/event-stream`. The LangChain chain's `.astream()` yields tokens as SSE events. Both the Streamlit frontend (via `requests` streaming) and the React frontend (via `EventSource` / `fetch` with `ReadableStream`) consume this endpoint for real-time token-by-token rendering.

---

## 7. API Endpoints

```text
POST   /collections                    Create topic collection
GET    /collections                    List all collections
GET    /collections/{topic}            Collection stats & doc list
DELETE /collections/{topic}            Delete collection + all data

POST   /collections/{topic}/upload     Upload document (multipart)
DELETE /collections/{topic}/docs/{id}  Remove single document

POST   /query                          Ask a question (full response)
GET    /query/stream                   Ask a question (SSE streaming)
GET    /query/history                  Recent queries (session-based)

POST   /extract-metadata               Infer title/author from file (stateless)

GET    /health                         System health (Qdrant, Ollama, embeddings)
```

---

## 8. Project Structure

```text
doctalk/
├── docker-compose.yml          # Starts backend + both frontends
├── Dockerfile                  # Backend image
├── pyproject.toml
├── .env.example
├── README.md
│
├── shared/
│   └── doctalk_shared/
│       └── models.py           # All Pydantic models (shared by backend + Streamlit)
│
├── app/
│   ├── main.py                 # FastAPI app, lifespan
│   ├── config.py               # pydantic-settings
│   │
│   ├── api/
│   │   ├── collections.py
│   │   ├── upload.py
│   │   ├── query.py            # POST /query + GET /query/stream (SSE)
│   │   └── health.py
│   │
│   ├── llm/
│   │   └── provider.py         # build_llm() factory — Ollama or DeepSeek
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
├── frontend-streamlit/         # Streamlit app (MVP / demo layer)
│   ├── app.py
│   ├── pages/
│   │   ├── 1_Upload.py
│   │   ├── 2_Chat.py
│   │   └── 3_Collections.py
│   └── requirements.txt
│
├── frontend-react/             # Next.js app (production UI / portfolio showcase)
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx        # Chat view (default landing)
│   │   │   ├── collections/
│   │   │   │   └── page.tsx    # Collection manager
│   │   │   └── upload/
│   │   │       └── page.tsx    # Upload page
│   │   ├── components/
│   │   │   ├── ChatWindow.tsx      # Message list + streaming token renderer
│   │   │   ├── MessageBubble.tsx   # User / assistant bubble with source badges
│   │   │   ├── SourceCard.tsx      # Source citation: filename, page, preview
│   │   │   ├── CollectionList.tsx  # Collection grid with stats
│   │   │   ├── UploadDropzone.tsx  # Drag-and-drop file upload
│   │   │   └── HealthBadge.tsx     # Live /health indicator
│   │   ├── hooks/
│   │   │   ├── useChat.ts          # SSE stream consumption + message state
│   │   │   └── useCollections.ts   # Collection CRUD via API
│   │   └── lib/
│   │       └── api.ts              # Typed API client (fetch wrapper)
│   └── Dockerfile
│
├── eval/
│   ├── test_dataset.json
│   ├── run_ragas.py
│   └── run_deepeval.py
│
├── tests/
│   ├── conftest.py
│   ├── factories.py
│   ├── test_loaders.py
│   ├── test_chunker.py
│   ├── test_api.py
│   ├── test_retrieval.py
│   └── test_registry.py
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

### Phase 3: Streamlit UI ✅

| Task                                    | Done |
| --------------------------------------- | ---- |
| Streamlit frontend — upload page        | ✅    |
| Streamlit frontend — chat page          | ✅    |
| Streamlit frontend — collection manager | ✅    |
| Collection stats endpoint               | ✅    |

### Phase 4: Provider Flexibility + Evaluation ← **current focus**

AI-first topics: LLM provider swap, eval frameworks, observability. Highest learning-value items for portfolio positioning.

| Task                                     | Done |
| ---------------------------------------- | ---- |
| Test Q&A dataset (20+ pairs)             | ✅    |
| RAGAS evaluation                         | ✅    |
| Structured logging (per-request trace)   | ✅    |
| DeepSeek API provider toggle             | ✅    |
| DeepEval integration                     | ❌    |
| Benchmark script                         | ❌    |
| SSE streaming endpoint (`/query/stream`) | ❌    |

#### SSE Streaming Endpoint

Required by the React frontend for real-time token rendering. Add to `app/api/query.py`:

```python
@router.get("/query/stream")
async def query_stream(question: str, topics: str | None = None):
    async def event_generator():
        async for token in chain.astream(question, topics):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

Streamlit can optionally consume this too; the existing POST `/query` endpoint stays unchanged.

### Phase 5: React Frontend

**Goal:** Production-quality chat UI that demonstrates the React/Python/AI stack combination directly. Both frontends run simultaneously — Streamlit on port 8501, React on port 3000, both pointing at the same FastAPI backend on port 8000.

**Why keep both:** Streamlit shows speed-of-iteration (built in hours); React shows production engineering (typed API client, streaming, component architecture). Having both in the same repo is itself a talking point in proposals.

| Task                                              | Done |
| ------------------------------------------------- | ---- |
| Next.js + Tailwind scaffold in `frontend-react/`  | ❌    |
| Typed API client `lib/api.ts` (from OpenAPI spec) | ❌    |
| `useChat` hook — SSE stream + message state       | ❌    |
| `ChatWindow` + `MessageBubble` — token streaming  | ❌    |
| `SourceCard` — citation (filename, page, preview) | ❌    |
| `useCollections` hook + `CollectionList`          | ❌    |
| `UploadDropzone` — drag-and-drop upload           | ❌    |
| `HealthBadge` — live backend health indicator     | ❌    |
| Docker service for React in `docker-compose.yml`  | ❌    |
| README screenshots: both UIs side-by-side         | ❌    |

**Key implementation notes:**

- `useChat` consumes `/query/stream` via the browser's `EventSource` API or `fetch` + `ReadableStream`; tokens appended to message state on each SSE event
- Sources arrive as a final SSE event after `[DONE]` — rendered as `SourceCard` components below the answer
- `lib/api.ts` mirrors the Pydantic models as TypeScript interfaces — generated once from the OpenAPI schema at `/openapi.json`, then maintained manually
- No external state library needed (React `useState` + `useReducer` sufficient for this scope)
- Tailwind for styling — matches Denis's existing Advanced-level skill, no new CSS framework to learn

### Phase 6: Code Quality — OOP vs Functional

Evaluate which classes justify being classes and which should be plain functions. A class is justified when construction cost (model load, connection open) must be paid once and the instance reused across calls.

| Class              | Holds shared state?                               | Verdict                           | Done |
| ------------------ | ------------------------------------------------- | --------------------------------- | ---- |
| `Reranker`         | Yes — `CrossEncoder` model loaded once at startup | Keep as class                     | ❌    |
| `Embedder`         | Yes — `SentenceTransformer` + sparse model        | Keep as class                     | ❌    |
| `VectorDB`         | Yes — Qdrant client + connection                  | Keep as class                     | ❌    |
| `DocRegistry`      | Yes — SQLite connection                           | Keep as class                     | ❌    |
| `IngestionService` | No own state — wraps injected collaborators       | Convert to module-level functions | ❌    |
| `search_service`   | Already module-level functions                    | ✅ Done                            | ✅    |
| `chain.py`         | Already module-level functions                    | ✅ Done                            | ✅    |

### Phase 7: Hardening + Polish

Infrastructure and presentation work — do after React frontend is solid.

| Task                                | Done |
| ----------------------------------- | ---- |
| Python 3.12 upgrade (PEP 695 types) | ❌    |
| Document delete endpoint            | ❌    |
| API key auth middleware             | ❌    |
| Sample data seeding script          | ❌    |
| Docker optimization                 | ❌    |
| README with screenshots (both UIs)  | ❌    |

#### Python 3.12 Upgrade

**Goal:** Adopt PEP 695 type syntax (`type`, `[T]` generics) for cleaner type annotations.

| Feature          | Old (3.11)                                     | New (3.12)                        |
| ---------------- | ---------------------------------------------- | --------------------------------- |
| Type alias       | `Sample: TypeAlias = dict[str, object]`        | `type Sample = dict[str, object]` |
| Generic function | `def first(xs: list[T]) -> T` + `TypeVar("T")` | `def first[T](xs: list[T]) -> T`  |
| Generic class    | `class Stack(Generic[T])`                      | `class Stack[T]`                  |

**Migration steps:**

1. `uv python install 3.12`
2. Update `pyproject.toml`: `requires-python = "==3.12.*"`
3. `uv sync`
4. Replace `TypeAlias` assignments and `TypeVar` boilerplate — see patterns above
5. `mise run dev-check`

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
├── test_loaders.py
├── test_chunker.py
├── test_api.py
├── test_retrieval.py
└── test_registry.py     # doc registry integration tests
```

### Key Patterns

- Each test gets a fresh SQLite session, rolled back on teardown
- Qdrant test collections are prefixed `test_` and deleted after the test
- `factory-boy` `SubFactory` handles relationships (e.g. chunks belonging to a document)
- `build()` for in-memory objects, `create()` to persist to DB

---

## 12. Future Extensions

- **Agentic layer:** LangGraph agent for autonomous multi-step retrieval (Phase 8 candidate)
- **Multi-tenant isolation:** Per-company API keys with collection-level access control
- **Web scraping loader:** URL ingestion alongside file upload
- **Azure deployment:** ACI/ACA for ComplianceCoder demo
- **Multi-LLM support:** Add Anthropic Claude + Google Gemini to `build_llm()` factory — signals multi-LLM-SDK capability now appearing in DACH job postings

---

## 13. Success Criteria

| Metric                                   | Target                                         |
| ---------------------------------------- | ---------------------------------------------- |
| Supports 4 document formats              | PDF, DOCX, MD, TXT all working                 |
| RAG answer accuracy (RAGAS faithfulness) | > 0.80                                         |
| RAG context relevancy (RAGAS)            | > 0.75                                         |
| Query response time (local, Ollama)      | < 5 seconds                                    |
| Query response time (DeepSeek API)       | < 3 seconds                                    |
| Docker Compose single-command startup    | `docker compose up` → backend + both UIs run   |
| API documentation                        | Auto-generated Swagger at `/docs`              |
| Test coverage                            | > 70% (loaders + API)                          |
| Both frontends functional                | Streamlit on :8501, React on :3000, same API   |
| GitHub README with demo GIF              | Portfolio-ready, showing both UIs side-by-side |
