# GigBid (AI-4016 Assignment II)

Multi-agent freelancer copilot: LangGraph agents, MCP servers, advanced RAG, a FastAPI and Next.js web app, and our own GigSim marketplace simulator.

These three docs are the source of truth. Read them before any work and follow them:

@1.PROJECT_SPECIFICATION.md
@2.ARCHITECTURE.md

## Current phase

**Phase 6: Web (Part D)** (see `1.PROJECT_SPECIFICATION.md` §8). Phases 0 to 5 were accepted on 2026-11-16. GigSim is frozen at tag `gigsim-v1`; CI fails if anything under `gigsim/` changes. Work on nothing beyond this phase until the user accepts it. The public URL https://gigbid-7txm.onrender.com serves only `/health` so far (Render free tier, `docs/RUNBOOK.md`).

Carried over from Phase 5:
- Done on main: bid and conversation graphs (C1), typed state and reducers (C2), hand-offs (C3), Critic loop and Compliance block, step and token budgets with `needs_attention` (C4, `agent/graphs/guard.py`), interrupt approve/edit/reject (C5), Postgres checkpointer with a crash/resume/replay exactly-once test (C6, `agent/checkpointing.py`), retries, fallback model and dead-letter (C7), style and outcome memory behind promotion rules (R7, `agent/memory/`), policy v2 as its own commit (`evals/results/policy_v2_diff.json`).
- Shortcuts: analyst, fit, pricing and critic nodes are rule-based (`shortcut:` comments). Outcome memory is promoted by `promote_outcome` but nothing calls it yet; the Phase 7 worker should, from GigSim proposal events. No live node uses the fallback model yet. The Postgres checkpointer test runs only in CI (no local Postgres).
- R&D C (`docs/RND_C.md`, `evals/results/rnd_c_dev.json`): n = 7 dev jobs only (Groq quota); ReAct and supervisor 0.857 accuracy. Our graph was 0.143 (bid on every job); after the evidence-score threshold (`evals/results/fit_threshold_dev.json`) and two risk signals it is 0.571 and skips the scam and the injection (tuned after seeing these jobs, so biased). Decision-metric numbers (`evals/runners/decision_eval.py`) are not produced yet. `agent/memory/promotion_rules.py` imports `mask_pii` from `data/pipeline/`.

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
