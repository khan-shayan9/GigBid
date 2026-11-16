# GigBid (AI-4016 Assignment II)

Multi-agent freelancer copilot: LangGraph agents, MCP servers, advanced RAG, a FastAPI and Next.js web app, and our own GigSim marketplace simulator.

These three docs are the source of truth. Read them before any work and follow them:

@1.PROJECT_SPECIFICATION.md
@2.ARCHITECTURE.md

## Current phase

**Phase 8: Report and portfolio** (see `1.PROJECT_SPECIFICATION.md` §8). Phases 0 to 7 were accepted (Phase 7 on 2026-11-16). GigSim is frozen at tag `gigsim-v1`; CI fails if anything under `gigsim/` changes. Work on nothing beyond this phase until the user accepts it. The public URL is https://gigbid-shayan.indiasouthcentral.cloudapp.azure.com (Azure for Students B2s VM, India South Central, `docker compose --profile public`, Caddy HTTPS; reviewer login `reviewer` preloaded with `ai_ml_engineer`). Deploy and redeploy steps are in `docs/RUNBOOK.md` (`infra/setup_vps.sh`; `az vm run-command` since Cloud Shell keeps no SSH key). The old Render URL serves only `/health`.

Carried over from Phase 7:
- Done on main: Arq worker with scout and outcome-sync crons and Redis run state (`worker/`, `apps/api/run_state.py`); outcomes promoted from GigSim proposal events and a live pipeline board over SSE; Langfuse Cloud tracing (`agent/tracing.py`, one trace per thread, node and tool spans, PII masked, FastAPI request spans blocked), trace links in the run viewer, cost and latency on analytics; smoke eval gates in CI (`make eval`), Playwright and `tsc` in CI, worker tests on Redis and Postgres; full compose with web and Caddy. Verified live: sign-in, analyse, draft, approve, submit, the board moving to Replied without a refresh, and traces in Langfuse.
- Fixed while deploying: stdio MCP servers get the API's environment; a blocked edit (proposal or reply) goes back to approval; Regenerate keeps the AI-assistance disclosure; the eval backend now searches the Portfolio server's default evidence types (no past proposals), so results before dd91de9 used inflated fit scores.
- Numbers: smoke eval bid F1 0.47, scam recall 0.25, injection attack success 0.0 (0.217 without the injection signal), all on 30 or 23 dev jobs (`evals/results/smoke_eval_dev.json`, `injection_dev.json`). `minimum_fit_score` is 0.55 (the user's choice; same decisions as 0.60 on all 565 dev jobs, 0.50 would give F1 0.414). `fit_threshold_dev.json` was rerun on the corrected backend and 0.65 still holds. `rnd_c_dev.json` and `cost_latency_dev.json` came from the old backend.
- Not done: R8/E5 budgets not declared (only 3 proposals measured, Groq daily cap); USD not computed (no model prices); writer-level injection eval (`evals/runners/injection_writer.py`) not run; no fallback model for the writer; the live agent bids on few jobs because the inbox shows every job, not only the persona's field.
- Architecture deviations to record in `2.ARCHITECTURE.md` when approved (not yet approved): the worker imports `apps/api` run state; Langfuse Cloud and Caddy; outcome polling by cron; the `evals` config section; `run_demo_eval.py` removed; full environment for stdio MCP servers; blocked edits loop back to approval; `infra/setup_vps.sh`.

Carried over from Phase 6:
- Done on main (35a7396): FastAPI routers, services and SSE (`apps/api/`), TS client generated from OpenAPI (`make api-client`), all nine Next.js screens (`apps/web/`), 8 Playwright flows at laptop and phone width (`make e2e`, real API with the fake marketplace in `tests/e2e/`), dry-run `preview` node, `list_proposals` tool, `FitReport.matrix`, hashed idempotency keys (`agent/idempotency.py`).
- Phase 7 must: move graph runs from API tasks to the Arq worker (`shortcut:` in `apps/api/services/runs.py`); call `promote_outcome` from proposal events and make the pipeline board update from events (it updates on refresh now); add Langfuse trace links and cost/latency (the run viewer and analytics say "not measured yet"); add the web service to compose; put Playwright and `tsc` in CI; verify a pending approval survives an API restart with `API_PERSISTENCE=postgres` (set in compose, untested).
- Not built: own-profile onboarding, Upwork OAuth in the UI (CLI login only). Stored but unused: hourly floor and weekly Connects budget. Uploads are saved per account in `data/uploads/<account>/` but the Portfolio server does not search them yet. Accounts that pick the same persona share its GigSim data.
- Tailwind is v3: v4 fails to build when the path contains `#`. Architecture deviations to record in `2.ARCHITECTURE.md` when approved: `preview` node, `FitReport.matrix`, `apps/api/services/`, `web` allowlist.

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
