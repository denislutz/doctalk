# DocTalk — Evaluation & Benchmarking

Explains how the three evaluation mechanisms work, what they measure, and why they are run together.

---

## What is evaluation in a RAG system?

A RAG system has two failure modes: it retrieves the wrong chunks, or it generates a bad answer from good chunks. Evaluation catches both. DocTalk runs two complementary frameworks — RAGAS and DeepEval — plus a latency benchmark. Each answers a different question.

| Tool      | Question it answers                                      | What it needs                        |
| --------- | -------------------------------------------------------- | ------------------------------------ |
| RAGAS     | How well does the pipeline perform statistically?        | Ground truth answers, retrieved chunks |
| DeepEval  | Why did this specific sample fail?                       | Ground truth answers, retrieved chunks, judge LLM |
| Benchmark | How fast is the pipeline end-to-end?                     | Running API, test questions          |

---

## The test dataset

All evaluations share a single dataset: `eval/test_dataset.json`. Each sample has four fields:

```text
question     — the natural language query
ground_truth — the correct, complete answer
topics       — which Qdrant collection(s) to search
notes        — context about what makes this sample interesting
```

The dataset currently covers the `austrian_economics` and `libertarianism` collections, with 20+ question/answer pairs spanning factual recall, multi-hop reasoning, and edge cases where the answer is partially or not covered by the indexed documents.

---

## Eval sources

Before any evaluation can run, the source documents must be indexed. The five markdown files in `eval/sources/` are the ground truth corpus — the eval pipeline indexes them on first run and skips them on subsequent runs (deduplication via `eval/doc_registry.db`). If Qdrant loses its state (restart, wipe), delete `eval/doc_registry.db` to force re-indexing.

---

## RAGAS

**Runner:** `eval/run_ragas.py`  
**Task:** `mise run eval-ragas`

RAGAS is a reference-free evaluation framework that scores the full RAG pipeline output against ground truth. It treats evaluation as a data pipeline: inputs go in, a set of LLM-assisted metrics come out, results are aggregated into a score per metric.

### Metrics

**Answer Relevancy** — does the generated answer address the question that was asked? RAGAS generates several paraphrased versions of the answer and measures how closely they reconstruct the original question. A low score means the answer went off-topic or was vague.

**Context Precision** — of the chunks retrieved, how many were actually useful? High precision means the retrieval pipeline surfaced mostly relevant material. Low precision means the top-k is cluttered with noise.

### What RAGAS does not tell you

RAGAS gives you aggregate numbers. If answer relevancy drops from 0.82 to 0.71 after a retrieval change, you know something regressed — but not which samples failed or why. That gap is where DeepEval comes in.

### Output

Results are written to `eval/results/ragas_<timestamp>.json`. The runner also prints a summary table to stdout.

---

## DeepEval

**Runner:** `eval/run_deepeval.py`  
**Task:** `mise run eval-deepeval`  
**Judge model:** DeepSeek, via `app/llm/deep_seek_deepeval.py`

DeepEval wraps each pipeline result in an `LLMTestCase` and runs a judge LLM against it. The judge reads the question, answer, retrieved chunks, and ground truth together and produces both a score and a natural-language reason for that score. This is the key difference from RAGAS — the reason string explains *why* a sample failed, not just that it did.

### Metrics

**Answer Relevancy** — same goal as the RAGAS metric, but judged by the LLM rather than by paraphrase similarity. The judge asks: does this answer actually address the question?

**Faithfulness** — does the answer stay within what the retrieved chunks say? A high faithfulness score means the LLM did not hallucinate — every claim in the answer is grounded in the context it was given. This is the most important metric for a RAG system with a compliance or legal use case.

**Contextual Recall** — do the retrieved chunks contain enough information to reconstruct the ground truth? A low score here points to a retrieval problem, not a generation problem — the right content was not surfaced.

### The judge model

The judge is a separate LLM from the one generating answers. DocTalk uses DeepSeek for judging (via `app/llm/deep_seek_deepeval.py`), which wraps the OpenAI-compatible DeepSeek API. The judge needs `DEEPSEEK_API_KEY` in `.env.local`.

### Threshold

All three metrics use `threshold=0.7`. Samples below this threshold appear in the failure details section of the printed summary, with the judge's reason string explaining the failure in plain language.

### Output

Results are written to `eval/results/deepeval_<timestamp>.json`. The runner prints an aggregate table (mean score per metric, ⚠ if below threshold) followed by per-sample failure details.

---

## Running both

**Task:** `mise run eval`

Runs `eval-ragas` and `eval-deepeval` in sequence. Use `--limit N` on individual runners during development to avoid burning API credits on the full dataset:

```text
mise run eval-ragas     -- --limit 3
mise run eval-deepeval  -- --limit 3
```

---

## Benchmark

**Runner:** `scripts/benchmark.py` (planned)  
**Status:** not yet implemented

The benchmark measures pipeline latency — not answer quality. It hits the live `POST /query` API with every question in the test dataset and records the timing fields the API already returns in `QueryResponse`:

```text
retrieval_time_ms   — dense + sparse search + RRF + rerank
generation_time_ms  — LLM token generation
total_time_ms       — wall clock end to end
```

It runs the full dataset twice — once with Ollama as the LLM provider and once with DeepSeek — and reports min/mean/p95/max per stage per provider. The success criteria targets from the tech plan (< 5s local, < 3s DeepSeek) are validated here.

### What it does not measure

The benchmark measures the backend in isolation. It does not measure streaming latency (time-to-first-token as perceived by the browser) — that requires the SSE endpoint and a client-side measurement, which belongs to the React frontend phase.

---

## Why RAGAS and DeepEval together

| | RAGAS | DeepEval |
| --- | --- | --- |
| Scoring method | Statistical / embedding-based | LLM-as-judge |
| Output granularity | Aggregate scores | Per-sample scores + reasons |
| Cost | Free (local models) | Requires judge LLM API call |
| Best for | Regression detection across pipeline changes | Diagnosing specific failure cases |
| Blind spot | Can't explain why a sample failed | Score can drift with judge model changes |

Run RAGAS after every significant retrieval or prompt change to catch regressions cheaply. Run DeepEval when the RAGAS numbers move to understand what changed and why.
