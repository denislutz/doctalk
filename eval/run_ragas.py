# ruff: noqa: E402
"""
RAGAS evaluation runner.

Usage:
    mise run eval                          # uses dev Qdrant (port 6333)
    mise run eval -- --env test            # uses test Qdrant (port 6335)
    uv run python eval/run_ragas.py
    uv run python eval/run_ragas.py --dataset eval/test_dataset.json
    uv run python eval/run_ragas.py --env test

Prerequisites:
    - Qdrant running with documents already indexed in the target collections
      (run `mise run test-env-up` first when using --env test)
    - Ollama running with the configured model available
    - eval/test_dataset.json populated with question/ground_truth/topics tuples
"""

import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

import argparse
import asyncio
import json
from pathlib import Path

from langchain_huggingface import HuggingFaceEmbeddings as LCHuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from pydantic import BaseModel
from ragas import EvaluationDataset, aevaluate
from ragas.dataset_schema import EvaluationResult, SingleTurnSample
from ragas.embeddings import _LangchainEmbeddingsWrapper
from ragas.executor import Executor
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import AnswerRelevancy, ContextPrecision
from ragas.run_config import RunConfig

from app.config import settings
from app.ingestion.embedder import Embedder
from app.ingestion.ingestion_service import IngestionService
from app.retrieval import chain as retrieval_chain
from app.retrieval import search_service
from app.retrieval.reranker import Reranker
from app.storage.doc_registry import DocRegistry
from app.storage.vector_db_client import VectorDB

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class Sample(BaseModel):
    question: str
    ground_truth: str
    topics: list[str]
    notes: str


class PipelineResult(BaseModel):
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str
    notes: str


_ENV_QDRANT_URLS = {
    "dev": settings.vector_db_url,
    "test": "http://localhost:6335",
}
_ENV_REGISTRY_PATHS = {
    "dev": "eval/doc_registry.db",
    "test": "eval/test_doc_registry.db",
}


def _build_services(env: str) -> tuple[VectorDB, Embedder, Reranker, DocRegistry, ChatOllama]:
    import time

    def _timed(label: str, fn):
        print(f"  loading {label}...", end="", flush=True)
        t = time.perf_counter()
        result = fn()
        print(f" {time.perf_counter() - t:.1f}s")
        return result

    qdrant_url = _ENV_QDRANT_URLS[env]
    registry_path = _ENV_REGISTRY_PATHS[env]
    print(f"Initializing services ({env})...")
    vector_db = _timed("VectorDB", lambda: VectorDB(qdrant_url))
    embedder = _timed("Embedder", lambda: Embedder(model_name=settings.embedding_model))
    reranker = _timed("Reranker", lambda: Reranker(model_name=settings.reranker_model))
    registry = _timed("DocRegistry", lambda: DocRegistry(db_path=registry_path))
    llm = _timed(
        "Ollama",
        lambda: ChatOllama(base_url=settings.langchain_llm_url, model=settings.default_llm_model),
    )
    return vector_db, embedder, reranker, registry, llm


async def index_documents(
    embedder: Embedder, registry: DocRegistry, vector_db_client: VectorDB
) -> list[dict]:
    """Index the documents in the vector database."""
    sources_dir = Path("eval/sources")
    service = IngestionService(
        embedder=embedder, registry=registry, vector_db_client=vector_db_client
    )
    paths = [p for p in sources_dir.iterdir() if p.is_file()]
    results = []
    for i, path in enumerate(paths, 1):
        topic = path.stem.split("__")[0]
        print(f"  [{i}/{len(paths)}] {path.name} → '{topic}'", end="", flush=True)
        result = await service.ingest(path=path, topic=topic, source_name=path.name)
        results.append(result)
        if result.get("skipped"):
            print(" (already indexed, skipped)")
        else:
            print(" ✓")
    print(f"  done — {len(results)} documents processed")
    return results


# ---------------------------------------------------------------------------
# Step 1 — Load test dataset
# ---------------------------------------------------------------------------


def load_dataset(path: Path) -> list[Sample]:
    """Load and validate the test dataset from a JSON file.

    Each entry must have: question (str), ground_truth (str), topics (list[str]).
    """

    result = []
    with path.open("r") as f:
        data = json.load(f)
        for item in data:
            result.append(Sample.model_validate(item))
    return result


# ---------------------------------------------------------------------------
# Step 2 — Run pipeline for a single sample
# ---------------------------------------------------------------------------


async def run_pipeline(
    sample: Sample,
    embedder: Embedder,
    vector_db_client: VectorDB,
    reranker: Reranker,
    langchain_llm: ChatOllama,
) -> PipelineResult:
    collection = sample.topics[0]
    question = sample.question

    dense_chunks, sparse_chunks = await asyncio.gather(
        search_service.search_collection_dense(
            question=question,
            collection=collection,
            embedder=embedder,
            vector_db=vector_db_client,
        ),
        search_service.search_collection_sparse(
            question=question,
            collection=collection,
            embedder=embedder,
            vector_db=vector_db_client,
        ),
    )
    fused_chunks = search_service.reciprocal_rank_fusion(
        dense_results=dense_chunks, sparse_results=sparse_chunks
    )
    ranked_chunks = reranker.rerank(question, fused_chunks)
    answer = await retrieval_chain.generate_answer(question, ranked_chunks, langchain_llm)

    return PipelineResult(
        question=question,
        answer=answer,
        contexts=[chunk.content for chunk in ranked_chunks],
        ground_truth=sample.ground_truth,
        notes=sample.notes,
    )


# ---------------------------------------------------------------------------
# Step 3 — Build RAGAS dataset from pipeline results
# ---------------------------------------------------------------------------


def build_ragas_dataset(results: list[PipelineResult]):
    samples = []
    for res in results:
        samples.append(
            SingleTurnSample(
                user_input=res.question,
                response=res.answer,
                retrieved_contexts=res.contexts,
                reference=res.ground_truth,
                rubrics={"notes": res.notes},
            )
        )
    return EvaluationDataset(samples=samples)


# ---------------------------------------------------------------------------
# Step 5 — Run RAGAS evaluation
# ---------------------------------------------------------------------------


async def run_ragas_eval(dataset, llm, embeddings) -> EvaluationResult | Executor:
    run_config = RunConfig(max_workers=1, timeout=300, max_retries=2)
    return await aevaluate(
        dataset=dataset,
        llm=llm,
        embeddings=embeddings,
        # Faithfulness disabled — mistral:7b can't produce the structured JSON these prompts require.
        # Re-enable once Claude API is wired in as the judge (Phase 4 Claude provider toggle).
        metrics=[AnswerRelevancy(), ContextPrecision()],
        run_config=run_config,
    )


# ---------------------------------------------------------------------------
# Step 6 — print results And save it.
# ---------------------------------------------------------------------------


def print_summary(result: EvaluationResult) -> None:
    df = result.to_pandas()
    metric_cols = [
        c
        for c in df.columns
        if c not in {"user_input", "response", "retrieved_contexts", "reference", "rubrics"}
    ]
    print("\n── RAGAS Results ──────────────────────")
    for col in metric_cols:
        score = df[col].mean()
        flag = "  ⚠" if score < 0.75 else ""
        print(f"  {col:<30} {score:.3f}{flag}")
    overall = df[metric_cols].mean().mean()
    print(f"  {'overall':<30} {overall:.3f}")
    print("───────────────────────────────────────")


def save_results(result: EvaluationResult, out_dir: Path) -> Path:
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"ragas_{timestamp}.json"
    records = result.to_pandas().to_dict(orient="records")
    out_path.write_text(json.dumps(records, indent=2))
    return out_path


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


async def main(dataset_path: Path, out_dir: Path, env: str, limit: int | None = None) -> None:
    vector_db_client, embedder, reranker, registry, langchain_llm = _build_services(env)

    print(f"Environment: {env}  (Qdrant: {_ENV_QDRANT_URLS[env]})")

    print("Indexing documents...")
    await index_documents(embedder=embedder, registry=registry, vector_db_client=vector_db_client)

    print(f"Loading dataset from {dataset_path}")
    samples = load_dataset(dataset_path)[:limit]
    print(f"  {len(samples)} samples loaded")

    print(f"\nRunning pipeline for {len(samples)} samples...")
    results: list[PipelineResult] = []
    for i, sample in enumerate(samples, 1):
        print(f"  [{i}/{len(samples)}] {sample.question[:70]}")
        result = await run_pipeline(
            sample,
            embedder=embedder,
            vector_db_client=vector_db_client,
            reranker=reranker,
            langchain_llm=langchain_llm,
        )
        results.append(result)
        print(f"         → {len(result.contexts)} chunks retrieved")

    print("\nBuilding RAGAS dataset...")
    dataset = build_ragas_dataset(results)

    print("Configuring RAGAS judge (Ollama/mistral:7b)...")
    judge_llm = LangchainLLMWrapper(
        ChatOllama(base_url=settings.langchain_llm_url, model="mistral:7b", format="json")
    )
    embeddings = _LangchainEmbeddingsWrapper(
        LCHuggingFaceEmbeddings(model_name=settings.embedding_model)
    )

    print(f"Running RAGAS evaluation ({len(samples)} samples × 3 metrics)...")
    ragas_result = await run_ragas_eval(dataset, judge_llm, embeddings)
    assert isinstance(ragas_result, EvaluationResult)

    print_summary(ragas_result)

    out_path = save_results(ragas_result, out_dir)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run RAGAS evaluation")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).parent / "test_dataset.json",
        help="Path to test_dataset.json",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).parent / "results",
        help="Directory to write result JSON files",
    )
    parser.add_argument(
        "--env",
        choices=["dev", "test"],
        default="dev",
        help="Target environment: dev (port 6333) or test (port 6335)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Evaluate only the first N samples (e.g. --limit 2 for fast feedback)",
    )
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    asyncio.run(main(args.dataset, args.out_dir, args.env, args.limit))
