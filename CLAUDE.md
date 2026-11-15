# GigBid (AI-4016 Assignment II)

Multi-agent freelancer copilot: LangGraph agents, MCP servers, advanced RAG, a FastAPI and Next.js web app, and our own GigSim marketplace simulator.

These three docs are the source of truth. Read them before any work and follow them:

@1.PROJECT_SPECIFICATION.md
@2.ARCHITECTURE.md
@3.AI_RULES.md

## Current phase

**Phase 5: Graphs and memory (Part C)** (see `1.PROJECT_SPECIFICATION.md` §8). Phases 0 to 4 were accepted on 2026-11-15. GigSim is frozen at tag `gigsim-v1`; CI fails if anything under `gigsim/` changes. Work on nothing beyond this phase until the user accepts it.

Carried over from Phase 4:
- Shipped retrieval is V1 (`rag.variant`); results and limits in `docs/RND_B.md`. Not run yet: the held-out split, full-dev check, judge calibration labels (user), USD prices (user).
- Reranker is MiniLM-L-12, not bge-reranker-v2-m3 (ADR 0005). The verifier runs on gpt-oss-120b and `rag_query` on qwen3.8-27b (gpt-oss-20b's daily quota ran out).

Carried over from Phase 3:
- Embeddings run through fastembed (`nomic-ai/nomic-embed-text-v1.5`, ADR 0004), not Ollama. The V0 index in `rag/index/memory.py` is in memory; Phase 4 moves it to pgvector.
- Portfolio ingestion (`rag/ingest/portfolio.py`) is a one-item-per-document shortcut; B1 replaces it. GitHub ingestion goes through the GitHub MCP server (`github_ingest` allowlist in `agent/config.yaml`).
- The writer's grounding check (`agent/nodes/writer.py`) works on cited ids only; claim-level verification is `rag/verify.py` (B3).
- Not done yet: the rewritten R&D A tool descriptions are not in the servers; the MCP servers are not in `docker compose`; Upwork live mode needs the user's sign-in before its tool map can be filled.
- Groq free tier allows 8,000 tokens a minute; long eval runs must cache and resume (see `evals/runners/rnd_a_tool_granularity.py`).

## Quick reminders

- The assignment brief is `../Assignment-II.pdf`. Never edit, rename or delete it.
- Raw Kaggle CSVs live in `data/raw/kaggle/` (368 MB). Never modify them. They are git-ignored (`data/raw/` in `.gitignore`).
- Never send, submit or spend Connects without an approved `interrupt()`.
- Never invent numbers. Cite `evals/results/`.
- Propose a commit at the end of each phase. Never add AI attribution to commits.
- After every major milestone (end of a phase or a large slice of one), report the work to the
  advisor model (Fable) and have it check the work before reporting to the user or proposing a
  commit. Fix what it finds; re-check large fixes with it.
