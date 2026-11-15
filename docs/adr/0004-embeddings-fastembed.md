# ADR 0004: Run nomic-embed-text through fastembed, not Ollama

Status: accepted (Phase 3)

## Context
The spec runs open embedding models (`nomic-embed-text`) locally through Ollama. The development
laptop (i5-6300U, 7.4 GB RAM, no usable GPU) cannot comfortably run the Ollama app beside the
rest of the stack, and the production VPS is short of memory too (spec §12).

## Decision
- Embeddings run in-process on CPU through `fastembed` (ONNX), one pinned dependency, using
  `nomic-ai/nomic-embed-text-v1.5`. The model stays the same open model; only the runtime changes.
- `models.embeddings` in `agent/config.yaml` names the provider and model; `fake` (a hashed bag of
  words) is for tests only. The nomic task prefixes (`search_document: `, `search_query: `) are
  added by our embedder, because fastembed does not add them.
- Vectors are cached on disk per model and text hash (`data/processed/embeddings/`) until Phase 4
  moves them to pgvector (ADR 0001).

## Consequences
- No Ollama service is needed for embeddings. Ollama remains an option for local LLMs.
- The first embedding of a portfolio is slow on this CPU; `python -m mcp_servers.portfolio.server
  warm` fills the cache ahead of time.
- The reranker (`bge-reranker-v2-m3`, Phase 4) can use the same runtime.
