# ruff: noqa: E402
"""
DeepEval evaluation runner.

Usage:
    uv run python eval/run_deepeval.py
    uv run python eval/run_deepeval.py --limit 3

Prerequisites:
    - Qdrant running with documents indexed (same as RAGAS eval)
    - DEEPSEEK_API_KEY set in .env
    - eval/test_dataset.json populated
"""

import logging
import os
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*position_ids.*")
logging.getLogger("deepeval").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
os.environ.setdefault("CONFIDENT_METRIC_LOGGING_VERBOSE", "0")

import argparse
import asyncio
import json
from pathlib import Path

from deepeval.metrics import AnswerRelevancyMetric, ContextualRecallMetric, FaithfulnessMetric
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.config import settings
from app.ingestion.embedder import Embedder
from app.ingestion.ingestion_service import IngestionService
from app.llm.deep_seek_deepeval import DeepSeekDeepevalLLM
from app.retrieval import chain as retrieval_chain
from app.retrieval import search_service
from app.retrieval.reranker import Reranker
from app.storage.doc_registry import DocRegistry
from app.storage.vector_db_client import VectorDB

# ---------------------------------------------------------------------------
# Types (same as run_ragas.py)
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


class SampleResult(BaseModel):
    question: str
    answer_relevancy_score: float | None = None
    answer_relevancy_reason: str | None = None
    faithfulness_score: float | None = None
    faithfulness_reason: str | None = None
    contextual_recall_score: float | None = None
    contextual_recall_reason: str | None = None


# ---------------------------------------------------------------------------
# Infra — unchanged from run_ragas.py
# ---------------------------------------------------------------------------

_ENV_QDRANT_URLS = {
    "dev": settings.vector_db_url,
    "test": "http://localhost:6335",
}
_ENV_REGISTRY_PATHS = {
    "dev": "eval/doc_registry.db",
    "test": "eval/test_doc_registry.db",
}


def _build_services(env: str) -> tuple[VectorDB, Embedder, Reranker, DocRegistry, BaseChatModel]:
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
    langchain_llm = _timed(
        "LLM",
        # TODO: replace with a dynamic llm service, pulling the current config
        lambda: ChatOpenAI(
            model=settings.deepseek_model,
            base_url=settings.deepseek_base_url,
            api_key=settings.deepseek_api_key or "none",
        ),
    )
    return vector_db, embedder, reranker, registry, langchain_llm


async def index_documents(
    embedder: Embedder, registry: DocRegistry, vector_db_client: VectorDB
) -> list[dict]:
    sources_dir = Path("eval/sources")
    ingest_service = IngestionService(
        embedder=embedder, registry=registry, vector_db_client=vector_db_client
    )
    # filter all files in the sources_dir
    all_files = [entry for entry in sources_dir.iterdir() if entry.is_file()]

    results = []
    for i, file in enumerate(all_files, 1):
        topic = file.stem.split("__")[0]
        print(f"  [{i}/{len(all_files)}] {file.name} → '{topic}'", end="", flush=True)
        result = await ingest_service.ingest(path=file, topic=topic, source_name=file.name)
        results.append(result)
        print(" (skipped)" if result.get("skipped") else " ✓")
    print(f"  done — {len(results)} documents processed")
    return results


def load_dataset(path: Path) -> list[Sample]:
    with path.open("r") as f:
        return [Sample.model_validate(item) for item in json.load(f)]


async def run_pipeline(
    *,
    sample: Sample,
    embedder: Embedder,
    vector_db_client: VectorDB,
    reranker: Reranker,
    llm: BaseChatModel,
) -> PipelineResult:
    collection = sample.topics[0]
    question = sample.question
    dense_chunks, sparse_chunks = await asyncio.gather(
        search_service.search_collection_dense(
            question=question, collection=collection, embedder=embedder, vector_db=vector_db_client
        ),
        search_service.search_collection_sparse(
            question=question, collection=collection, embedder=embedder, vector_db=vector_db_client
        ),
    )
    fused_chunks = search_service.reciprocal_rank_fusion(
        dense_results=dense_chunks, sparse_results=sparse_chunks
    )
    ranked_chunks = reranker.rerank(question, fused_chunks)
    answer = await retrieval_chain.generate_answer(question, ranked_chunks, llm)
    return PipelineResult(
        question=question,
        answer=answer,
        contexts=[chunk.content for chunk in ranked_chunks],
        ground_truth=sample.ground_truth,
        notes=sample.notes,
    )


# ---------------------------------------------------------------------------
# DeepEval logic — implement these three
# ---------------------------------------------------------------------------


def build_test_cases(results: list[PipelineResult]) -> list:
    return [
        LLMTestCase(
            input=result.question,
            actual_output=result.answer,
            retrieval_context=result.contexts,
            expected_output=result.ground_truth,
        )
        for result in results
    ]


def run_eval(test_cases: list, judge_model: DeepEvalBaseLLM) -> list[SampleResult]:
    results = []
    n = len(test_cases)
    ar = AnswerRelevancyMetric(threshold=0.7, model=judge_model, verbose_mode=False)
    fa = FaithfulnessMetric(threshold=0.7, model=judge_model, verbose_mode=False)
    cr = ContextualRecallMetric(threshold=0.7, model=judge_model, verbose_mode=False)

    for i, test_case in enumerate(test_cases, 1):
        print(f"  [{i}/{n}] {test_case.input[:70]}", flush=True)
        ar.measure(test_case)
        print(f"         relevancy={ar.score:.2f}", end="", flush=True)
        fa.measure(test_case)
        print(f"  faithfulness={fa.score:.2f}", end="", flush=True)
        cr.measure(test_case)
        print(f"  recall={cr.score:.2f}")

        results.append(
            SampleResult(
                question=test_case.input,
                answer=test_case.actual_output,
                contexts=test_case.retrieval_context,
                ground_truth=test_case.expected_output,
                answer_relevancy_score=ar.score,
                answer_relevancy_reason=ar.reason,
                faithfulness_score=fa.score,
                faithfulness_reason=fa.reason,
                contextual_recall_score=cr.score,
                contextual_recall_reason=cr.reason,
            )
        )
    return results


def print_summary(results: list[SampleResult]) -> None:
    metrics = [
        ("answer_relevancy", "Answer Relevancy"),
        ("faithfulness", "Faithfulness"),
        ("contextual_recall", "Contextual Recall"),
    ]

    print("\n── Aggregate Scores ─────────────────────────────")
    for key, label in metrics:
        scores = [s for r in results if (s := getattr(r, f"{key}_score")) is not None]
        mean = sum(scores) / len(scores) if scores else 0.0
        flag = " ⚠" if mean < 0.7 else ""
        print(f"  {label:<22} {mean:.3f}{flag}")

    print("\n── Failures (score < 0.7) ───────────────────────")
    any_failure = False
    for r in results:
        for key, label in metrics:
            score = getattr(r, f"{key}_score")
            reason = getattr(r, f"{key}_reason")
            if score is not None and score < 0.7:
                any_failure = True
                print(f"  [{label}] score={score:.3f}")
                print(f"  Q: {r.question[:80]}")
                print(f"  → {reason}")
                print()
    if not any_failure:
        print("  None.")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def save_results(results: list[SampleResult], out_dir: Path) -> Path:
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"deepeval_{timestamp}.json"
    out_path.write_text(json.dumps([r.model_dump() for r in results], indent=2))
    return out_path


async def main(dataset_path: Path, out_dir: Path, env: str, limit: int | None = None) -> None:
    vector_db_client, embedder, reranker, registry, langchain_llm = _build_services(env)
    print(f"Environment: {env}  (Qdrant: {_ENV_QDRANT_URLS[env]})")

    print("Indexing documents...")
    await index_documents(embedder=embedder, registry=registry, vector_db_client=vector_db_client)

    print(f"Loading dataset from {dataset_path}")
    samples = load_dataset(dataset_path)[:limit]
    print(f"  {len(samples)} samples loaded")

    print(f"\nRunning RAG pipeline for {len(samples)} samples...")
    pipeline_results: list[PipelineResult] = []
    for i, sample in enumerate(samples, 1):
        print(f"  [{i}/{len(samples)}] {sample.question[:70]}")
        result = await run_pipeline(
            sample=sample,
            embedder=embedder,
            vector_db_client=vector_db_client,
            reranker=reranker,
            llm=langchain_llm,
        )
        pipeline_results.append(result)
        print(f"         → {len(result.contexts)} chunks retrieved")

    print("\nBuilding LLMTestCase objects...")
    test_cases = build_test_cases(pipeline_results)

    judge_model = DeepSeekDeepevalLLM()

    print(f"Running DeepEval metrics ({len(test_cases)} samples × 3 metrics)...")
    eval_results = run_eval(test_cases, judge_model)

    print_summary(eval_results)
    out_path = save_results(eval_results, out_dir)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run DeepEval evaluation")
    parser.add_argument("--dataset", type=Path, default=Path(__file__).parent / "test_dataset.json")
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).parent / "results")
    parser.add_argument("--env", choices=["dev", "test"], default="dev")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    asyncio.run(main(args.dataset, args.out_dir, args.env, args.limit))
