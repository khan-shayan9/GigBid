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
