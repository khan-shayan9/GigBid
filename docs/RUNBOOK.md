# Runbook

## Local development
1. Install uv 0.11.8 (pinned in `pyproject.toml`).
2. `cp .env.example .env` and fill in local values. Never commit `.env`.
3. `uv sync --frozen` installs the pinned dependencies.
4. `make lint test` (or, without `make`: `uv run ruff check .` and `uv run pytest -q`).
5. `make api` runs the API on port 8000 with reload.

## Web app (Phase 6)
- **Run it:** `make gigsim` (GigSim), `make api` (FastAPI on 8000), `make web` (Next.js on 3000;
  `cd apps/web && npm install` once). The browser talks only to Next.js, which proxies `/api/*`
  to `API_URL`, so the session cookie is first-party and SSE needs no CORS.
- **Accounts:** `APP_USERS` holds `name=salt:hash` pairs (scrypt); make one with
  `uv run python -m apps.api.auth.users <name> <password>`. `APP_SECRET_KEY` signs the session
  cookie. After sign-in, onboarding picks a persona (`api.personas` in `agent/config.yaml`).
- **Runs:** graph threads are `<account>:bid:<job_id>` and `<account>:conv:<message_id>`. A run
  segment (start, or the resume after an approval) runs as a task in the API process
  (shortcut until the Phase 7 worker). `API_PERSISTENCE=memory` keeps checkpoints in memory, so
  restarting the API loses them; `postgres` keeps them in `DATABASE_URL`.
- **Streaming:** `GET /runs/{thread_id}/stream` sends a `snapshot` from the checkpoint, then one
  `node` event per finished node (LangGraph `updates` mode), `interrupt`, `end`. It sends
  `Cache-Control: no-transform` because Next.js gzip would otherwise buffer the stream.
- **Typed client:** `make api-client` writes `apps/web/openapi.json` and regenerates
  `apps/web/src/lib/api/schema.d.ts`; `tests/integration/test_api.py` fails when it is stale.
- **Tests:** `make e2e` runs Playwright (laptop and Pixel 7 widths) against the real API served
  by `tests/e2e/serve.py` with a fake marketplace and scripted models (no GigSim or Groq needed).
  The HTML report lands in `apps/web/playwright-report/`.
- **Uploads:** saved per account in `data/uploads/<account>/` (git-ignored). They are not
  searched by drafts yet: the Portfolio server indexes only `data/personas/<persona>/`.
- **Tailwind v3, not v4:** v4's stylesheet resolver fails when the project path contains `#`
  (this repo's local folder `A#2-Agentic`).

## Docker
`docker compose up` at the repo root (or `make dev`) starts the stack in `infra/docker-compose.yml`:
the API on port 8000, Postgres with pgvector, and Redis. `GET /health` answers once the API is up.

## GigSim (marketplace simulator, port 8081)
- **Run:** `make gigsim` (or `docker compose up gigsim`). Run from the repo root (default paths
  are relative) with one uvicorn worker (the rate limiter and fault counters are in memory).
- **Users and tokens:** users are the three personas in `data/gigsim_seed/sim_config.json`.
  `GIGSIM_TOKENS=user=token,...` gives each a Bearer token; `GIGSIM_ADMIN_TOKEN` unlocks
  `POST /admin/clock/advance` and `POST /admin/reset`. With no tokens every call is 401.
- **Tuning (data, not code):** `sim_config.json` holds the seed, time scale (sim minutes per real
  minute), fault rate, rate limit, starting Connects, default client preferences and the client
  simulation weights, thresholds, delays and replies. `GIGSIM_FAULTS=off` disables seeded 5xx.
- **Clock:** sim time runs from `GIGSIM_EPOCH` (or the first start, remembered in SQLite). Jobs
  appear when their `release_after_min` passes. Fix `GIGSIM_EPOCH` for repeatable runs.
  `GET /time` shows sim time to users.
- **State:** SQLite at `GIGSIM_DB_PATH` (compose: the `gigsimdata` volume). It holds proposals,
  events, messages, the Connects ledger and idempotency keys, so a restart keeps them.
  `POST /admin/reset` clears all of it and puts the clock back to minute 0 (use before evals).
- **Policy:** `GIGSIM_POLICY=data/policy_pack/v1.yaml` (default) or `v2.yaml`. Switching is a
  restart with a new env value; no code changes.
- **Client simulation:** seeded rules by default. For the LLM mode set `client_sim.mode` to
  `llm` and `GIGSIM_LLM_BASE_URL`, `GIGSIM_LLM_MODEL`, `GIGSIM_LLM_API_KEY` (any
  OpenAI-compatible endpoint: Ollama, Groq). Any LLM error falls back to the rules.
- **Grader data:** put files in our seed format in a folder and add it:
  `GIGSIM_SEED_DIRS=data/gigsim_seed,/path/to/grader`. Ids that collide with ours stop startup;
  in that case point `GIGSIM_SEED_DIRS` at the grader folder alone. See `docs/DATA_CARD.md` §8.
- **Failures clients must handle:** 429 with `Retry-After` (per user), seeded 503s (retry with
  the same `Idempotency-Key`; a write may have committed before the 503 and the retry replays it),
  402 `insufficient_connects`, 409 `already_submitted` / `already_applied` /
  `idempotency_conflict` / `daily_submit_limit`, 422 `policy_violation`.
- **Known limits:** sending a message never triggers a client reply (client messages come from
  seeded conversations and proposal lifecycles).

## Marketplace MCP server (port 8082)
- **Run:** `make mcp-marketplace` (Streamable HTTP at `/mcp`, needs GigSim running) or
  `uv run python -m mcp_servers.marketplace.server` (stdio, for MCP Inspector and Claude Desktop;
  acts as `MARKETPLACE_STDIO_USER`).
- **Auth:** HTTP callers send `Authorization: Bearer <token>` from `MARKETPLACE_MCP_TOKENS`; the
  server calls GigSim with that user's `GIGSIM_TOKENS` entry. No token, no call (401).
- **Limits and retries:** `MARKETPLACE_RATE_PER_MINUTE` per user (default 20, under GigSim's
  limit). Calls to GigSim retry 429 (after `Retry-After`, at most 10 s) and 5xx (0.5, 1, 2 s),
  four tries in all; writes retry with the caller's idempotency key. After that the tool fails
  with `marketplace_unavailable` (degraded mode).
- **Writes** default to `dry_run=true`, which returns the exact draft, message or submission and
  its Connects cost without changing anything.
- **Audit log:** `MARKETPLACE_AUDIT_LOG`, one JSON line per call (user, tool, arguments, result,
  trace id), PII masked, append-only. Callers pass `_meta.trace_id` to tie a call to their trace.

## Portfolio MCP server (port 8083)
- **Run:** `make mcp-portfolio` (HTTP, `PORTFOLIO_MCP_TOKENS`) or
  `uv run python -m mcp_servers.portfolio.server` (stdio, acts as `PORTFOLIO_STDIO_USER`).
- **What it serves:** read-only, and only `data/personas/<user>/` for the caller's user. Tools
  `search_evidence`, `get_case_study`, `list_skills`; resources `portfolio://case/{id}` and
  `portfolio://proposal/{id}`; prompts `draft_proposal` and `map_requirements`.
- **Embeddings:** `models.embeddings` in `agent/config.yaml` (fastembed running
  `nomic-ai/nomic-embed-text-v1.5` on CPU; no Ollama). The first search for a user downloads the
  model once (about 0.5 GB, into `fastembed_cache` in the system temp folder; set
  `FASTEMBED_CACHE_PATH` to keep it elsewhere) and embeds that user's portfolio; vectors are
  cached in `data/processed/embeddings/`, so later starts reuse them. Tests use a fake embedder;
  `REAL_EMBEDDINGS=1 uv run pytest mcp_servers/portfolio` also runs the real-model check.
  Run `uv run python -m mcp_servers.portfolio.server warm` once after the portfolio changes, so
  no first search waits on embedding (ADR 0004).
- **Search defaults:** `search_evidence` searches case studies, CV sections, repo files and
  reviews. Past proposals are opt-in (`filters.types=["proposal"]`), since they show what was
  pitched, not what was done. The CV's "Not my thing" section is never evidence; `list_skills`
  returns it as `not_offered`.
- **Index:** V0 (dense top-k cosine) in process memory; pgvector replaces it in Phase 4.

## Workspace MCP server (port 8084)
- **Run:** `make mcp-workspace` (HTTP, `WORKSPACE_MCP_TOKENS`) or
  `uv run python -m mcp_servers.workspace.server` (stdio, acts as `WORKSPACE_STDIO_USER`).
- **Local mock:** working hours are weekdays 09:00-17:00 in the user's profile timezone; only
  GigBid's own holds are busy. Holds and email drafts live in
  `data/processed/workspace/<user>.json`. Email drafts are saved, never sent.
- **Tools:** `find_free_slots` (timezone-aware window, at most 14 days), `hold_slot` (tentative)
  and `draft_email`; both writes take an idempotency key and default to `dry_run=true`.

## Agent MCP client and the Phase 3 acceptance run
- **Client:** `agent/mcp_client.py`. Nodes reach MCP servers only through it, and only the tools in
  their `mcp.allowlists` entry in `agent/config.yaml` (anything else raises `ToolNotAllowed`).
  `mcp.transport: stdio` starts each server as a local process for one user; `http` calls the
  running servers with that user's `<PREFIX>_MCP_TOKENS` token.
  stdio is for local development only (each server loads `.env` itself); compose and the
  deploy use `http`.
- **Failures:** each call has a `mcp.timeout_s` limit. Timeouts and transport errors are retried
  (`mcp.retries`, backoff 0.5 s, 1 s, ...) only for read-only tools and writes that carry an
  idempotency key. A server that does not start, or a `marketplace_unavailable` /
  `rate_limited` refusal, raises `ToolUnavailable` (degraded mode: queue the work, try later);
  other refusals raise `ToolFailed` and are not retried.
- **Models:** `agent/llm.py` builds each node's model from the active profile and
  `llm_providers` (Groq by default; key from `GROQ_API_KEY`).
- **Acceptance run:** with GigSim running (`make gigsim`), `make draft-one` lets the writer draft
  one proposal for the first GigSim job matching `--query` (default `chatbot`), using only
  `search_evidence` evidence, and writes `evals/results/phase3_grounded_draft.json`
  (`grounded: true` when every cited id came from `search_evidence`).

## Live mode (Upwork) and GitHub MCP
- **Upwork live:** set `MARKETPLACE_MODE=upwork_live` and `TOKEN_ENCRYPTION_KEY`, then sign each
  user in once with `uv run python -m mcp_servers.marketplace.adapters.upwork_live login --user
  <user>` (open the printed URL, approve, paste the address you land on). Tokens are stored
  encrypted in `data/processed/oauth/`. The command prints Upwork's tools; map them under
  `marketplace.upwork_live.tools` in `agent/config.yaml`. Live mode only creates drafts.
  Schedules stay conservative: read only through the Marketplace server's per-user limiter.
- **GitHub:** set `GITHUB_PERSONAL_ACCESS_TOKEN` (fine-grained, public repos, read-only). The
  client calls GitHub's hosted server read-only with the `repos` toolset (`docs/TOOLS.md`).

## R&D A (tool granularity)
`uv run python -m evals.runners.rnd_a_tool_granularity` runs 120 model calls (40 tasks x 3 tool
sets). On Groq's free tier (8,000 tokens a minute) it takes about half an hour; it caches each
call in `data/processed/rnd_a/` and resumes after an interruption.

## Public deploy (Phase 0)
The thin `/health` deploy runs on Render's free tier at https://gigbid-7txm.onrender.com/health.
It redeploys on every push to `main`. It was created as a Render Web Service with these settings
(`render.yaml` holds the same settings as a Blueprint):
- Runtime: Docker; branch `main`; root directory empty
- Dockerfile path `./infra/docker/api.Dockerfile`; build context `.`
- Health check path `/health`; instance type Free; no environment variables

Free services sleep when idle, so the first request after a pause takes longer. The full stack
moves to a VPS running `docker compose` in Phase 7.

TODO: Document rate limits, recovery and degraded mode (Phases 3 to 7).
