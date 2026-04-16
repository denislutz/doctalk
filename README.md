# DocTalk

Self-hosted RAG system for querying company documents via natural language. Upload PDFs, DOCX, Markdown, and CSV files into topic collections and ask questions across them. No data leaves your network.

## Requirements

- [mise](https://mise.jdx.dev) — manages Python, uv, and docker-compose versions
- [Docker](https://docs.docker.com/get-docker/) — for Qdrant and Ollama

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

- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Frontend: http://localhost:8501

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Default | Description |
|---|---|---|
| `API_KEY` | `changeme` | Header auth key (`X-API-Key`) |
| `ANTHROPIC_API_KEY` | — | Optional Claude API fallback |
| `OLLAMA_MODEL` | `mistral:7b` | Local LLM model |
| `QDRANT_HOST` | `localhost` | Qdrant host |

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

| Layer | Technology |
|---|---|
| API | FastAPI + Pydantic |
| Vector DB | Qdrant |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 (local) |
| RAG | LangChain |
| LLM | Ollama (Mistral 7B) — Claude API optional |
| Frontend | Streamlit |
| Evaluation | RAGAS + DeepEval |
