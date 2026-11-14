# ADR 0001: pgvector as the vector store

Status: accepted (Phase 0)

## Context
GigBid already needs Postgres for app data, the LangGraph checkpointer and the LangGraph store.
Retrieval needs dense vectors (`nomic-embed-text`) for the RAG variants in Phase 4. Everything runs
on one VPS with `docker compose`, so every extra service costs memory.

## Decision
Store embeddings in Postgres with the pgvector extension (`pgvector/pgvector:pg16` image).

## Consequences
- One database to run, back up and scope by tenant; no second store to keep in sync.
- Fewer index types than a dedicated vector database; enough for three persona corpora.
- Swapping the store later stays inside `rag/index/` (`2.ARCHITECTURE.md` §15).
