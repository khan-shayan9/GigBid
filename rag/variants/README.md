One component per file: v0_naive (dense), v1_decompose (requirement split), v2_hybrid (BM25 +
dense, RRF), v3_rerank (cross-encoder), v8_corrective (LangGraph grade/rewrite/refuse loop).
A variant is a set of switches in `rag.variants` (agent/config.yaml); `rag/retriever.py` assembles it.
