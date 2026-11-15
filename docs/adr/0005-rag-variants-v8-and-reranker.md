# ADR 0005: RAG variants as switches, V8 inside rag/, and the reranker used

Status: accepted (Phase 4)

## Context
- Part B asks for V0 plus at least four variants, one command to rerun the comparison, and a V8
  corrective loop "in LangGraph". `2.ARCHITECTURE.md` §10 says `rag/` does not know about graphs.
- The spec names `bge-reranker-v2-m3`. On the development CPU (i5-6300U), its int8 build scored
  about 2 seconds per (job post, chunk) pair, measured while the first evaluation was running.
  Reranking 10–20 candidates for each of ~100 jobs per variant would have taken hours.
- The dev laptop has no Docker or Postgres (spec §9 names pgvector).

## Decision
- **Variants are switches.** Each variant (`rag.variants` in `agent/config.yaml`) is a set of
  switches over components in `rag/variants/`: `decompose` (V1), `hybrid` (V2), `rerank` (V3) and
  `corrective` (V8). V0 is all switches off. `rag/retriever.py` assembles the pipeline, and
  `RAG_VARIANT` or `rag.variant` picks the shipped one.
- **V8 lives in `rag/variants/v8_corrective.py`.** It is a small, self-contained LangGraph
  `StateGraph` (retrieve, grade, rewrite, refuse) that imports nothing from `agent/`. The search
  function, the rewrite model and its prompt are passed in. "rag does not know about graphs" is
  read as "rag does not know about the agent's graphs".
- **V1 merges round-robin by rank, not by RRF.** A unit test showed that RRF across
  per-requirement lists favours generic items that rank moderately for every requirement over
  the best item for each requirement.
- **Reranker:** `Xenova/ms-marco-MiniLM-L-12-v2` (open, fastembed ONNX; an ad-hoc timing on 30 long pairs gave 0.18 s a pair against 1.25 s
  for the int8 m3),
  reranking the top 10. `BAAI/bge-reranker-v2-m3-int8` is a one-line config change.
- **Index:** `rag/index/pgvector.py` (docker compose, CI service container) and
  `rag/index/memory.py` (local evaluation and tests) run the same exact cosine search behind
  `rag.index` / `RAG_INDEX`.

## Consequences
- The reported V3 and V8 numbers are for MiniLM, not `bge-reranker-v2-m3`. The report says so.
- Local evaluation numbers come from the memory index. CI checks that pgvector returns the same
  ranking (`tests/integration/test_pgvector.py`).
