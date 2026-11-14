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
The thin `/health` deploy runs on Render's free tier from `render.yaml`. To set it up:
1. Push the repo to GitHub.
2. In Render: New, then Blueprint, then pick the repo. Render builds `infra/docker/api.Dockerfile`.
3. Open `https://<service>.onrender.com/health`.

Free services sleep when idle, so the first request after a pause takes longer. The full stack
moves to a VPS running `docker compose` in Phase 7.

TODO: Document rate limits, recovery and degraded mode (Phases 3 to 7).
