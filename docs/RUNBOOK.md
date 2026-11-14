# Runbook

## Local development
1. Install uv 0.11.8 (pinned in `pyproject.toml`).
2. `cp .env.example .env` and fill in local values. Never commit `.env`.
3. `uv sync --frozen` installs the pinned dependencies.
4. `make lint test` (or, without `make`: `uv run ruff check .` and `uv run pytest -q`).
5. `make api` runs the API on port 8000 with reload.

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
