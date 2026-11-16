.PHONY: worker api-client web e2e eval-rag eval-table install dev api gigsim mcp-marketplace mcp-portfolio mcp-workspace draft-one test lint eval seed demo

install:
	uv sync --frozen

dev:
	docker compose up --build

api:
	uv run uvicorn apps.api.main:app --reload --port 8000 --env-file .env

# OpenAPI schema -> apps/web/src/lib/api/schema.d.ts (generated; never edit by hand)
api-client:
	uv run python -m apps.api.export_openapi
	cd apps/web && npm run gen:api

web:
	cd apps/web && npm run dev

# Playwright against the real API with a fake marketplace and scripted models (tests/e2e/)
e2e:
	cd apps/web && npx playwright test

# Arq worker (needs RUN_MODE=worker, Postgres and Redis; see docs/RUNBOOK.md)
worker:
	uv run arq worker.main.WorkerSettings

gigsim:
	uv run uvicorn --factory gigsim.app:create_app --port 8081

mcp-marketplace:
	uv run python -m mcp_servers.marketplace.server http

mcp-portfolio:
	uv run python -m mcp_servers.portfolio.server http

mcp-workspace:
	uv run python -m mcp_servers.workspace.server http

draft-one:
	uv run python -m evals.runners.draft_one

test:
	uv run pytest -q

lint:
	uv run ruff check .

# Smoke eval: 30 dev jobs up to the writer, no model calls; fails below the gates (CI).
eval:
	uv run python -m evals.runners.smoke_eval --check

# Part B: every retrieval variant, the ablation, proposal quality and outcomes, then the table.
# Model replies and reranker scores are cached in data/processed/eval_cache/, so a rerun is cheap.
eval-rag:
	uv run python -m evals.runners.rag_eval --per-persona 20
	uv run python -m evals.runners.ablation --per-persona 20 --pipeline v1_v2_v3
	uv run python -m evals.runners.proposal_eval --per-persona 3
	uv run python -m evals.runners.results_table

eval-table:
	uv run python -m evals.runners.results_table

seed:
	uv run python -m data.pipeline.build_seed

demo:
	@echo "make demo is built once the bid graph runs end to end (Phase 5)." && exit 1
