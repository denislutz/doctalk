# DocTalk — Search Concepts

Explains how the three search mechanisms work, what they store, and why they are combined.

---

## What is a chunk?

A chunk is a slice of a document — not a single word, not the whole file. In DocTalk: max 512 tokens (~380 words, a few paragraphs), min 50 tokens. The chunker splits on semantic boundaries first (page breaks, headings), then applies a token-window pass for anything too large.

Each chunk is stored in Qdrant as a single **point** with three representations of the same text:

```text
"leave policy: employees must submit leave requests. leave requests require 30 days notice."
        │                         │                                   │
   payload                  dense vector                       sparse vector
  (raw text)               (what it means)                  (what words, how often)
        │                         │                                   │
  stored as-is             384 floats from                  {hash("leave"): 3,
  returned to user          the neural model                 hash("requests"): 2,
  as source citation        — opaque to humans               hash("policy"): 1, ...}
```

---

## Dense search

**Model:** `all-MiniLM-L6-v2` (bi-encoder)
**Similarity:** cosine on 384-dimensional vectors
**Finds:** semantically similar text — paraphrases, synonyms, related concepts
**Misses:** exact rare terms not seen together in training data

The bi-encoder asks: *do these two texts belong to the same topic?* It maps both the chunk and the query into the same 384-dim space. Chunks whose vectors point in the same direction score high.

---

## Sparse / BM25 search

**Method:** hash-based term frequency, dot product similarity
**Finds:** exact keyword matches — names, codes, article numbers, domain jargon
**Misses:** semantic meaning, synonyms, paraphrases

### How the sparse vector is built (ingest time)

Given the chunk text:

> "leave policy: employees must submit leave requests. leave requests require 30 days notice."

1. **Tokenize** — split into individual terms

2. **Count term frequency (TF)**

   ```text
   "leave": 3,  "requests": 2,  "policy": 1,  "employees": 1,  ...
   ```

3. **Hash each term to a stable integer ID**

   ```python
   hash("leave")    % 2**20  →  891042
   hash("requests") % 2**20  →  445521
   hash("policy")   % 2**20  →  124857
   ```

4. **Store as a sparse vector** — only the terms that appear, not all 2²⁰ possible indices:

   ```python
   {
     "indices": [891042, 445521, 124857, ...],
     "values":  [3.0,    2.0,    1.0,   ...]
   }
   ```

Most of the ~1 million possible indices are zero. Only the terms present in the chunk are stored — that's why it's called *sparse*.

### How scoring works (query time)

Query: **"what is the leave policy?"**

Same process — tokenize and hash the question:

```python
{"indices": [891042, 124857], "values": [1.0, 1.0]}
#              "leave"          "policy"
```

Qdrant computes the **dot product**: multiply matching indices, sum the results:

```text
"leave":  1.0 × 3.0 = 3.0
"policy": 1.0 × 1.0 = 1.0
total score = 4.0
```

A chunk mentioning "policy" but not "leave" scores `1.0`. Our chunk scores `4.0` — higher because "leave" dominates it.

Qdrant does this efficiently via an **inverted index** — a lookup table per term ID:

```text
891042 ("leave")  → [chunk_A: 3.0, chunk_C: 1.0, chunk_F: 2.0]
124857 ("policy") → [chunk_A: 1.0, chunk_D: 4.0]
```

Only chunks that share at least one token with the query are ever touched. Chunks with no matching term are skipped entirely.

### Limitation: no stemming

"require" and "requirements" hash to different integers — sparse search treats them as unrelated. Dense search handles this trivially because both words land near each other in embedding space. This is the core reason to run both.

---

## Cross-encoder re-ranking

**Model:** `ms-marco-MiniLM-L-6-v2`
**Role:** reranker, not retriever — operates on candidates already retrieved
**Asks:** *does this specific text directly answer this specific question?*

The cross-encoder reads both the question and each chunk together in a single forward pass — slower than the bi-encoder but far more accurate at judging direct relevance. It scores the top ~20 fused candidates and returns the top 5.

### Example

Query: **"what is the leave policy?"**

RRF has already merged the dense and sparse lists into 4 candidates. Chunk B ranked high because it appeared in both lists consistently — but it doesn't directly answer the question.

**RRF output (input to reranker):**

| rank | chunk | content |
| --- | --- | --- |
| 0 | A | "employees must submit leave requests 30 days in advance" |
| 1 | B | "HR department manages all employee benefits and policies" |
| 2 | C | "the annual leave policy grants 20 days per year" |
| 3 | D | "sick leave requires a doctor's note after 3 days" |

The cross-encoder scores each (question, chunk) pair together:

```text
("what is the leave policy?", chunk A) → 0.91
("what is the leave policy?", chunk B) → 0.23
("what is the leave policy?", chunk C) → 0.97
("what is the leave policy?", chunk D) → 0.61
```

**Reranker output (top_k=3):**

| rank | chunk | score |
| --- | --- | --- |
| 0 | C | 0.97 |
| 1 | A | 0.91 |
| 2 | D | 0.61 |

Chunk B is cut — consistent cross-list presence got it into the candidate pool, but the cross-encoder found it doesn't answer the question. Chunk C jumps from position 2 to 0 because it contains "leave policy" in a definitional sentence. These are the chunks passed to the LLM as context.

---

## Reciprocal Rank Fusion (RRF)

Dense and sparse searches run in parallel and each return a ranked list of chunks. RRF merges them without relying on raw scores — cosine similarity and dot product are on incompatible scales and can't be added directly. Instead it uses only the **rank position**:

```text
score = 1 / (k + rank + 1)
```

Applied to both lists and summed per chunk. With `k=60` the scores across ranks are compressed into a narrow range:

```text
rank 0  →  1 / (60 + 0 + 1)  =  1/61   =  0.0164
rank 1  →  1 / (60 + 1 + 1)  =  1/62   =  0.0161
rank 5  →  1 / (60 + 5 + 1)  =  1/66   =  0.0152
rank 19 →  1 / (60 + 19 + 1) =  1/80   =  0.0125
```

Rank 0 and rank 19 differ by only `0.0039` — being #1 in one list is not enough to dominate.

### Three scenarios

**Chunk A — ranked #1 in dense, absent from sparse:**

```text
0.0164 + 0      =  0.0164
```

**Chunk B — ranked #5 in dense, ranked #3 in sparse:**

```text
0.0152 + 0.0156 =  0.0308
```

**Chunk C — ranked #1 in both:**

```text
0.0164 + 0.0164 =  0.0328
```

Chunk B beats Chunk A despite never being #1 in anything — consistent relevance across both methods outranks dominance in just one. This is the core insight of RRF.

### What k controls

With `k=1` (low), rank 0 scores `0.500` and rank 5 scores `0.143` — being #1 dominates everything. With `k=60` (standard), the field is nearly flat and the cross-encoder reranker that runs next can do its job properly. RRF just needs to produce a good candidate pool, not a perfect ordering.

---

## Why all three together

| Stage | What it does | Why it's not enough alone |
| --- | --- | --- |
| Dense search | Catches meaning, synonyms, paraphrases | Misses exact rare terms |
| Sparse search | Catches exact terms, codes, jargon | Misses semantic similarity |
| RRF merge | Combines both ranked lists fairly | — |
| Cross-encoder | Re-scores top candidates by direct relevance | Too slow to run on all chunks |

---

## Full flow — end to end

**User query:** "What is the leave policy?"

### Step 1 — Dense search

The query is embedded by `all-MiniLM-L6-v2` into a 384-float vector. Qdrant does cosine similarity against all stored dense vectors and returns the top 20 chunks by directional closeness. Chunk C ("the annual leave policy grants 20 days per year") scores high because the embedding space places it near the query meaning.

### Step 2 — Sparse / BM25 search (parallel)

The query is tokenized and hashed: `{hash("leave"): 1.0, hash("policy"): 1.0}`. Qdrant hits its inverted index — only chunks that share at least one term are touched. Dot product is computed per matching chunk. Returns top 20 by keyword overlap score.

### Step 3 — RRF merge

Two ranked lists come in — cosine scores and dot-product scores are on incompatible scales, so raw scores are thrown away. Each chunk gets `1/(60 + rank + 1)` from each list, summed. A chunk present in both lists (even mid-ranked in each) beats a chunk that dominated only one. Output: top 10 chunks by RRF score.

### Step 4 — Cross-encoder reranking

The cross-encoder (`ms-marco-MiniLM-L-6-v2`) reads each `(query, chunk)` pair together in a single forward pass — it sees both at once, unlike the bi-encoder which embeds them separately. Scores each of the 10 candidates for direct answer relevance. Returns top 5. Chunk B ("HR manages all employee benefits") gets cut here — it was consistent enough to survive RRF but the cross-encoder can see it doesn't answer the question.

### Step 5 — LLM generation

The top 5 chunks are injected as context into the prompt. The LLM is instructed to answer only from the provided context and cite sources. It never sees the other 15+ chunks that didn't make the cut.

### Why this sequence and not a different order

RRF must come before the cross-encoder because the cross-encoder is too slow to run on all chunks in the collection — it only works on a small candidate pool. Dense + sparse produce that pool cheaply in parallel; RRF merges them fairly; the cross-encoder then does the expensive precision work on just the survivors.
