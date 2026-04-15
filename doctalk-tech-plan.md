# DocTalk — Self-Hosted Talk-to-Your-Data RAG System

## Technical Project Plan

**Type:** Learning Project + Portfolio Piece + ComplianceCoder Demo  
**Duration:** 5 weeks (~20h/week = ~100h total)  
**Status:** Planning

---

## 1. Project Goal

Build a self-hosted, GDPR-compliant RAG application where companies upload documents (DOCX, PDF, MD, CSV), organize them into topic collections, and query across their data via natural language. No data leaves the company network.

**Target demo scenario:** A compliance officer uploads policy documents, HR guidelines, and financial CSVs into separate collections — then asks cross-collection questions like "What are our data retention requirements for employee records?" and gets sourced answers.

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
│  │ (FastAPI)│   │ │ CSV      │ │    ┌────────▼─────────┐  │
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

| Layer                | Technology                                       | Why                                                                         |
| -------------------- | ------------------------------------------------ | --------------------------------------------------------------------------- |
| **Language**         | Python 3.11+                                     | Market demand (89%), all libraries native                                   |
| **API Framework**    | FastAPI + Pydantic                               | Market demand (39%), async, typed, auto-docs                                |
| **Vector DB**        | Qdrant (Docker)                                  | Already know from Workspace Genie, collection isolation, metadata filtering |
| **Embeddings**       | `sentence-transformers/all-MiniLM-L6-v2` (local) | Free, fast, GDPR-compliant, already used in Workspace Genie                 |
| **RAG Framework**    | LangChain                                        | Market demand (50%), chains + retrievers + memory                           |
| **LLM**              | Ollama (Mistral 7B) local + Claude API toggle    | Self-hosted default, API option for quality comparison                      |
| **Doc Processing**   | `python-docx`, `PyMuPDF`, `markdown`, `pandas`   | One loader per format, all pure Python                                      |
| **Frontend**         | Streamlit (MVP)                                  | Fast to build, good enough for demo                                         |
| **Containerization** | Docker Compose                                   | Qdrant + Ollama + App in one `docker compose up`                            |
| **Evaluation**       | RAGAS + DeepEval                                 | Market demand (17%), differentiating skill                                  |
| **Testing**          | pytest + httpx (async)                           | Standard Python testing                                                     |

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
    "page_number": 5,           # PDF/DOCX
    "section_header": "3.1 Leave Policy",  # MD/DOCX
    "row_range": null,          # CSV: "rows 10-25"
    "ingested_at": "2026-04-15T10:30:00Z",
    "content_preview": "First 100 chars..."
}
```

### FastAPI Data Models (Pydantic)

```python
# --- Request Models ---

class DocumentUpload(BaseModel):
    topic: str                    # collection/topic name
    description: str | None = None

class QueryRequest(BaseModel):
    question: str
    topics: list[str] | None = None   # None = search all
    top_k: int = 5
    use_reranking: bool = True

# --- Response Models ---

class SourceChunk(BaseModel):
    filename: str
    format: str
    page_number: int | None
    section_header: str | None
    content_snippet: str
    relevance_score: float

class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    tokens_used: int
    retrieval_time_ms: float
    generation_time_ms: float

class CollectionInfo(BaseModel):
    topic: str
    document_count: int
    chunk_count: int
    formats: list[str]
    created_at: str
```

---

## 5. Document Ingestion Pipeline (Detail)

### 5.1 Format-Specific Loaders

Each loader returns a list of `DocumentChunk` objects with format-aware metadata.

```python
# Unified chunk output
@dataclass
class DocumentChunk:
    content: str
    metadata: dict    # format-specific metadata
```

| Format   | Library            | Chunking Strategy                                                                                                            | Metadata Extracted                        |
| -------- | ------------------ | ---------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| **PDF**  | `PyMuPDF` (fitz)   | Split by pages → then by paragraphs within page. Respect headings as boundaries.                                             | page_number, total_pages, has_images      |
| **DOCX** | `python-docx`      | Split by heading hierarchy (H1→H2→H3 = section boundaries). Paragraphs within sections.                                      | section_header, heading_level, style_name |
| **MD**   | `markdown` + regex | Split by `##` heading markers. Code blocks kept intact as single chunks.                                                     | section_header, heading_level, has_code   |
| **CSV**  | `pandas`           | Group rows into chunks of N rows (default 25). Include column headers in every chunk. Optionally chunk by a grouping column. | column_names, row_range, total_rows       |

### 5.2 Chunking Config

```python
CHUNK_CONFIG = {
    "max_chunk_size": 512,       # tokens (not chars)
    "chunk_overlap": 50,         # token overlap between chunks
    "min_chunk_size": 50,        # skip tiny fragments
    "csv_rows_per_chunk": 25,    # rows grouped per CSV chunk
}
```

### 5.3 Embedding & Storage

```python
# Embedding model (runs locally, no API calls)
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("all-MiniLM-L6-v2")  # 384 dimensions

# Embed + upsert to Qdrant
embeddings = model.encode(chunk_texts, show_progress_bar=True)
qdrant_client.upsert(
    collection_name=collection_name,
    points=[
        PointStruct(id=uuid4().hex, vector=emb, payload=meta)
        for emb, meta in zip(embeddings, chunk_metadata)
    ]
)
```

---

## 6. RAG Query Pipeline (Detail)

### 6.1 Retrieval Strategy

```
User Question
  │
  ├─▶ Dense Search (embedding similarity via Qdrant)
  │     └─ top_k=20 candidates
  │
  ├─▶ Sparse/Keyword Search (BM25 via Qdrant's built-in)
  │     └─ top_k=20 candidates
  │
  └─▶ Merge + Reciprocal Rank Fusion (RRF)
        └─ combined top_k=10
            │
            ▼
      Cross-Encoder Re-Ranking
      (sentence-transformers/cross-encoder/ms-marco-MiniLM-L-6-v2)
            │
            ▼
      Top 5 chunks → Context Window
            │
            ▼
      LLM Generation (with source attribution prompt)
            │
            ▼
      Structured Response (answer + sources)
```

### 6.2 Multi-Collection Query

When `topics=None` or multiple topics specified, search runs in parallel across collections and merges results before re-ranking.

```python
async def search_across_collections(
    question: str,
    topics: list[str] | None,
    top_k: int = 5
) -> list[ScoredChunk]:
    collections = topics or await list_all_collections()
    tasks = [search_collection(q, col, top_k=20) for col in collections]
    all_results = await asyncio.gather(*tasks)
    merged = reciprocal_rank_fusion(all_results)
    reranked = cross_encoder_rerank(question, merged, top_k=top_k)
    return reranked
```

### 6.3 Generation Prompt

```python
SYSTEM_PROMPT = """You are a document assistant for a company's internal knowledge base.
Answer the user's question based ONLY on the provided context chunks.
Rules:
- If the context doesn't contain the answer, say "I couldn't find this in the indexed documents."
- Always cite which document and section/page your answer comes from.
- Use [Source: filename, page/section] format for citations.
- Be precise and factual. Do not hallucinate.
- If data comes from CSV, present numbers accurately.
"""

USER_PROMPT = """
Context:
{formatted_chunks}

Question: {user_question}
"""
```

### 6.4 Conversation Memory

LangChain `ConversationBufferWindowMemory` (last 5 exchanges) for follow-up questions.

```python
memory = ConversationBufferWindowMemory(
    k=5,
    return_messages=True,
    memory_key="chat_history"
)
```

---

## 7. API Endpoints

```
POST   /collections                    Create topic collection
GET    /collections                    List all collections
GET    /collections/{topic}            Collection stats & doc list
DELETE /collections/{topic}            Delete collection + all data

POST   /collections/{topic}/upload     Upload document (multipart)
DELETE /collections/{topic}/docs/{id}  Remove single document

POST   /query                          Ask a question (single or cross-collection)
POST   /query/stream                   Streaming response (SSE)
GET    /query/history                  Recent queries (session-based)

GET    /health                         System health (Qdrant, Ollama, embeddings)
```

### Auth (Simple MVP)

API key header: `X-API-Key: <key>` — configured via environment variable. Enough for self-hosted demo. JWT/OAuth deferred to Phase 2.

---

## 8. Project Structure

```
doctalk/
├── docker-compose.yml          # Qdrant + Ollama + App
├── Dockerfile
├── pyproject.toml              # Poetry/pip dependencies
├── .env.example
├── README.md
│
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, CORS, lifespan
│   ├── config.py               # Settings via pydantic-settings
│   │
│   ├── api/
│   │   ├── collections.py      # Collection CRUD endpoints
│   │   ├── upload.py           # Document upload endpoint
│   │   ├── query.py            # Query + streaming endpoints
│   │   └── health.py           # Health check
│   │
│   ├── ingestion/
│   │   ├── loader_pdf.py       # PyMuPDF loader
│   │   ├── loader_docx.py      # python-docx loader
│   │   ├── loader_md.py        # Markdown loader
│   │   ├── loader_csv.py       # Pandas CSV loader
│   │   ├── chunker.py          # Adaptive chunking logic
│   │   └── embedder.py         # sentence-transformers wrapper
│   │
│   ├── retrieval/
│   │   ├── search.py           # Dense + sparse + RRF merge
│   │   ├── reranker.py         # Cross-encoder re-ranking
│   │   └── chain.py            # LangChain QA chain + memory
│   │
│   ├── llm/
│   │   ├── ollama_client.py    # Local Ollama (Mistral)
│   │   └── claude_client.py    # Claude API fallback
│   │
│   ├── models/
│   │   ├── requests.py         # Pydantic request models
│   │   └── responses.py        # Pydantic response models
│   │
│   └── storage/
│       └── qdrant_client.py    # Qdrant connection + helpers
│
├── eval/
│   ├── test_dataset.json       # Q&A pairs for evaluation
│   ├── run_ragas.py            # RAGAS evaluation script
│   └── run_deepeval.py         # DeepEval evaluation script
│
├── tests/
│   ├── test_loaders.py         # Unit tests per format
│   ├── test_chunker.py         # Chunking edge cases
│   ├── test_api.py             # FastAPI endpoint tests
│   └── test_retrieval.py       # Search quality tests
│
├── sample_data/
│   ├── policies.pdf
│   ├── handbook.docx
│   ├── README.md
│   └── employees.csv
│
└── scripts/
    ├── seed_demo.py            # Load sample_data into collections
    └── benchmark.py            # Response time + quality benchmarks
```

---

## 9. Dependencies

```toml
[tool.poetry.dependencies]
python = "^3.11"

# API
fastapi = "^0.115"
uvicorn = {extras = ["standard"], version = "^0.30"}
pydantic = "^2.7"
pydantic-settings = "^2.3"
python-multipart = "^0.0.9"

# Document Processing
python-docx = "^1.1"
PyMuPDF = "^1.24"
markdown = "^3.6"
pandas = "^2.2"

# RAG / AI
langchain = "^0.2"
langchain-community = "^0.2"
qdrant-client = "^1.9"
sentence-transformers = "^3.0"

# LLM Clients
ollama = "^0.3"
anthropic = "^0.30"

# Evaluation
ragas = "^0.1"
deepeval = "^0.21"

# Utilities
tiktoken = "^0.7"         # Token counting for chunk sizing
httpx = "^0.27"           # Async HTTP client

[tool.poetry.group.dev.dependencies]
pytest = "^8.2"
pytest-asyncio = "^0.23"
ruff = "^0.5"
```

---

## 10. Docker Compose

```yaml
version: "3.9"
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    restart: unless-stopped

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    # After first start: docker exec -it ollama ollama pull mistral:7b
    restart: unless-stopped

  app:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - qdrant
      - ollama
    volumes:
      - ./uploads:/app/uploads
    restart: unless-stopped

volumes:
  qdrant_data:
  ollama_data:
```

---

## 11. Phased Build Plan

### Phase 1: Ingestion Pipeline (Week 1–2, ~20h)

| Task                                                     | Time | Output                                     |
| -------------------------------------------------------- | ---- | ------------------------------------------ |
| Project setup (Poetry, FastAPI skeleton, Docker Compose) | 3h   | Running `/health` endpoint                 |
| Qdrant client wrapper (create/list/delete collections)   | 3h   | Collection CRUD working                    |
| PDF loader + tests (PyMuPDF)                             | 3h   | PDF → chunks with page metadata            |
| DOCX loader + tests (python-docx)                        | 3h   | DOCX → chunks with heading metadata        |
| MD loader + tests                                        | 2h   | MD → chunks with section metadata          |
| CSV loader + tests (pandas)                              | 3h   | CSV → row-group chunks with column headers |
| Adaptive chunker (token-based, format-aware)             | 3h   | Respects boundaries, configurable size     |
| Embedder + Qdrant upsert                                 | 2h   | End-to-end: file → chunks → vectors stored |
| Upload API endpoint (multipart file + topic)             | 2h   | `POST /collections/{topic}/upload` working |

**Phase 1 checkpoint:** Upload any of the 4 formats, see chunks in Qdrant dashboard.

### Phase 2: Query Engine (Week 2–3, ~20h)

| Task                                    | Time | Output                          |
| --------------------------------------- | ---- | ------------------------------- |
| Dense search (Qdrant vector similarity) | 2h   | Basic semantic search working   |
| BM25/sparse search (Qdrant keyword)     | 3h   | Keyword search working          |
| Reciprocal Rank Fusion merge            | 2h   | Hybrid results merged           |
| Cross-encoder re-ranker                 | 3h   | Top-k re-ranked by relevance    |
| LangChain QA chain + system prompt      | 3h   | Question → sourced answer       |
| Ollama client (Mistral 7B)              | 2h   | Local LLM generation            |
| Claude API client (toggle)              | 1h   | API fallback option             |
| Conversation memory (5-turn window)     | 2h   | Follow-up questions work        |
| Query API endpoint + streaming (SSE)    | 2h   | `POST /query` + `/query/stream` |

**Phase 2 checkpoint:** Ask questions, get answers with source citations. Compare Ollama vs Claude quality.

### Phase 3: Multi-Collection + UI (Week 3–4, ~20h)

| Task                                           | Time | Output                           |
| ---------------------------------------------- | ---- | -------------------------------- |
| Multi-collection parallel search               | 3h   | Cross-topic queries work         |
| Collection stats endpoint                      | 1h   | Doc counts, formats, sizes       |
| Document delete (remove from Qdrant by doc_id) | 2h   | `DELETE` endpoint working        |
| Streamlit frontend — upload page               | 3h   | Drag-and-drop upload to topic    |
| Streamlit frontend — chat page                 | 4h   | Chat UI with source display      |
| Streamlit frontend — collection manager        | 2h   | View/delete collections and docs |
| API key auth middleware                        | 1h   | Simple header-based auth         |
| Sample data seeding script                     | 2h   | Demo dataset with 4 formats      |
| README with screenshots                        | 2h   | Portfolio-ready documentation    |

**Phase 3 checkpoint:** Full working demo. Upload → organize → query → see sources.

### Phase 4: Evaluation + Hardening (Week 4–5, ~20h)

| Task                                                       | Time | Output                      |
| ---------------------------------------------------------- | ---- | --------------------------- |
| Create test Q&A dataset (20+ pairs across formats)         | 3h   | Ground truth for evaluation |
| RAGAS evaluation (faithfulness, relevancy, context recall) | 4h   | Metrics dashboard           |
| DeepEval integration (hallucination, answer correctness)   | 3h   | Second eval framework       |
| Benchmark script (response time, tokens, cost)             | 2h   | Performance numbers         |
| Error handling (bad files, empty chunks, Qdrant down)      | 3h   | Graceful failures           |
| Logging (structured, per-request trace)                    | 2h   | Debuggable in production    |
| Docker optimization (multi-stage build, health checks)     | 2h   | Clean compose setup         |
| Final testing pass + edge cases                            | 1h   | Stable release              |

**Phase 4 checkpoint:** Eval scores documented. Portfolio-ready with metrics.

---

## 12. Skills Learned (Mapped to Job Matrix)

| Skill                                                   | Depth Gained                                 | Market Demand | Before → After                   |
| ------------------------------------------------------- | -------------------------------------------- | ------------- | -------------------------------- |
| **Python** (file I/O, async, data parsing)              | 4 formats, edge cases, binary files          | 89%           | Intermediate → **Advanced**      |
| **RAG pipeline** (full end-to-end)                      | Ingest → chunk → embed → retrieve → generate | 72%           | Intermediate → **Advanced**      |
| **LangChain** (chains, retrievers, memory)              | Production chain with streaming + memory     | 50%           | Intermediate → **Advanced**      |
| **FastAPI** (file upload, SSE, auth, async)             | Real API with 10+ endpoints                  | 39%           | Intermediate → **Advanced**      |
| **Vector DBs / Qdrant** (collections, metadata, hybrid) | Multi-collection, hybrid search, filtering   | 39%           | Intermediate → **Advanced**      |
| **Embeddings** (local models, cross-encoders)           | Bi-encoder + cross-encoder re-ranking        | 44%           | Intermediate → **Advanced**      |
| **LLM Evaluation** (RAGAS, DeepEval)                    | Full eval suite with metrics                 | 17%           | None → **Intermediate**          |
| **Docker Compose** (multi-service)                      | 3-service stack                              | 39%           | Advanced → Advanced (reinforced) |
| **Ollama / Local LLMs** (Mistral)                       | Self-hosted inference                        | 11%           | Beginner → **Intermediate**      |

---

## 13. Future Extensions (Not in Scope)

These are deferred but noted for later phases or spin-off projects:

- **Agentic layer:** LangGraph agent that decides which collections to search, asks clarifying questions, or triggers follow-up searches autonomously
- **Multi-tenant isolation:** Per-company API keys with collection-level access control (→ WhatsApp RAG SaaS reuse)
- **Web scraping loader:** Add URL ingestion alongside file upload
- **Fine-tuning pipeline:** Use Q&A logs to fine-tune embedding model for domain-specific retrieval
- **React frontend:** Replace Streamlit with proper React UI (already expert)
- **Azure deployment:** ACI/ACA deployment for ComplianceCoder demo (→ Azure skill)

---

## 14. Success Criteria

| Metric                                   | Target                                |
| ---------------------------------------- | ------------------------------------- |
| Supports 4 document formats              | PDF, DOCX, MD, CSV all working        |
| RAG answer accuracy (RAGAS faithfulness) | > 0.80                                |
| RAG context relevancy (RAGAS)            | > 0.75                                |
| Query response time (local, Mistral 7B)  | < 5 seconds                           |
| Query response time (Claude API)         | < 3 seconds                           |
| Docker Compose single-command startup    | `docker compose up` → everything runs |
| API documentation                        | Auto-generated Swagger at `/docs`     |
| Test coverage                            | > 70% (loaders + API)                 |
| GitHub README with demo GIF              | Portfolio-ready                       |
