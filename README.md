# DocTalk

Self-hosted RAG system for querying company documents via natural language. Upload PDFs, DOCX, Markdown, and CSV files into topic collections and ask questions across them. No data leaves your network.

## Requirements

- [mise](https://mise.jdx.dev) — manages Python, uv, and docker-compose versions (`brew install mise`)
- [Docker](https://docs.docker.com/get-docker/) — for Qdrant and Ollama (`brew install --cask docker`)

## Quick Start

```bash
# 1. Install dependencies (Python 3.11, uv, docker-compose)
mise install

# 2. Create .env from example and set your API key
cp .env.example .env

# 3. Install Python packages
mise run setup

# 4. Start infrastructure (Qdrant + Ollama)
mise run dev

# 5. Pull the Mistral 7B model (first time only, ~4GB)
mise run ollama-pull-init

# 6. Start the API server
mise run api

# 7. Start the frontend (separate terminal)
mise run frontend
```

- API: <http://localhost:8000>
- API docs: <http://localhost:8000/docs>
- Frontend: <http://localhost:8501>

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable           | Default      | Description                   |
| ------------------ | ------------ | ----------------------------- |
| `API_KEY`          | `changeme`   | Header auth key (`X-API-Key`) |
| `DEEPSEEK_API_KEY` | —            | DeepSeek API key              |
| `OLLAMA_MODEL`     | `mistral:7b` | Local LLM model               |
| `QDRANT_HOST`      | `localhost`  | Qdrant host                   |

## VS Code Extensions

Install these for the best Python experience:

| Extension         | ID                            | Purpose                                     |
| ----------------- | ----------------------------- | ------------------------------------------- |
| Python            | `ms-python.python`            | Core Python support                         |
| Pylance           | `ms-python.vscode-pylance`    | Fast IntelliSense (Pyright)                 |
| Mypy Type Checker | `ms-python.mypy-type-checker` | Matches `mise run typecheck` exactly        |
| Ruff              | `charliermarsh.ruff`          | Matches `mise run lint` + `mise run format` |

> Note: Pylance uses Pyright under the hood, which can diverge from mypy. Install the Mypy extension and set `"python.typeCheckingMode": "off"` in `.vscode/settings.json` to see the same errors as `mise run check`.

## Development

```bash
mise run api          # FastAPI with hot reload
mise run frontend     # Streamlit UI
mise run test         # Run tests
mise run lint         # Ruff linter
mise run format       # Ruff formatter
mise run typecheck    # mypy
mise run quality      # All of the above
```

## Dependency Management

```bash
mise run add <pkg>        # Add a dependency
mise run add-dev <pkg>    # Add a dev dependency
mise run remove <pkg>     # Remove a dependency
mise run update           # Upgrade all deps + regenerate lockfile
mise run show-tree        # Show dependency tree
```

## Design & Architecture

- [spec/doctalk-tech-plan.md](spec/doctalk-tech-plan.md) — full technical specification, pipeline design, data model, and build status
- [spec/search-concepts.md](spec/search-concepts.md) — how dense search, BM25, RRF fusion, and cross-encoder reranking work
- [spec/eval-concepts.md](spec/eval-concepts.md) — how RAGAS, DeepEval, and the benchmark measure pipeline quality

---

## Evaluation Results

Evaluated on a 20-question test set covering two document collections (Austrian Economics, Libertarianism). The pipeline runs hybrid dense+sparse search with RRF fusion and cross-encoder reranking.

See [spec/eval-concepts.md](spec/eval-concepts.md) for a full explanation of what each metric measures and why the frameworks are used together.

### RAGAS — statistical pipeline scoring

Judged locally with Mistral 7B. Measures retrieval and answer quality without an external API.

| Metric            | Score     |
| ----------------- | --------- |
| Context Precision | **0.971** |
| Answer Relevancy  | **0.860** |

**Context Precision (0.971)** — retrieved chunks are highly relevant and correctly ranked. Hybrid search + reranking surfaces the right content.

**Answer Relevancy (0.860)** — answers are on-topic; occasional verbosity leaves room for prompt tuning.

### DeepEval — LLM-as-judge with failure reasons

Judged by DeepSeek API. Adds a faithfulness check and returns a natural-language reason for each failure.

| Metric            | Score     |
| ----------------- | --------- |
| Answer Relevancy  | **0.961** |
| Faithfulness      | **0.986** |
| Contextual Recall | **0.938** |

**Faithfulness (0.986)** — the LLM almost never hallucinates; answers stay within the retrieved context.

**Contextual Recall (0.938)** — two failures traced to ground-truth answers referencing content (exact quotes, secondary detail) not present in the indexed source documents — a dataset gap, not a retrieval bug.

**Answer Relevancy (0.961)** — one failure on a multi-topic comparative question; the pipeline answered each concept separately rather than addressing the commonality.

### Benchmark

Latency benchmarking across providers (Ollama vs DeepSeek) is planned — see [spec/eval-concepts.md](spec/eval-concepts.md).

> Run `mise run eval-ragas` or `mise run eval-deepeval` to reproduce. Use `-- --limit N` to cap sample count. Results saved to `eval/results/`.

---

## Full Docker Stack

To run everything in Docker (including the app):

```bash
mise run docker-up        # Build and start all services
mise run docker-status    # Check health of all services
mise run docker-logs      # Tail all logs
mise run docker-down      # Stop everything
```

## Project Structure

```text
doctalk/
├── app/
│   ├── api/              # FastAPI route handlers
│   ├── ingestion/        # Document loaders + chunker + embedder
│   ├── retrieval/        # Search, re-ranking, LangChain QA chain
│   ├── llm/              # Ollama + Claude clients
│   ├── models/           # Pydantic request/response models
│   └── storage/          # Qdrant client wrapper
├── frontend/             # Streamlit UI
├── eval/                 # RAGAS + DeepEval evaluation scripts
├── tests/                # pytest test suite
├── scripts/              # Seed data + benchmarks
├── docker-compose.yml
├── mise.toml             # Tool versions + task runner
└── pyproject.toml        # Python dependencies (uv)
```

## Tech Stack

| Layer      | Technology                                     |
| ---------- | ---------------------------------------------- |
| API        | FastAPI + Pydantic                             |
| Vector DB  | Qdrant                                         |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 (local) |
| RAG        | LangChain                                      |
| LLM        | Ollama (Mistral 7B) — Claude API optional      |
| Frontend   | Streamlit                                      |
| Evaluation | RAGAS + DeepEval                               |
