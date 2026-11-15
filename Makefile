.PHONY: install dev api gigsim mcp-marketplace mcp-portfolio mcp-workspace draft-one test lint eval seed demo

install:
	uv sync --frozen

dev:
	docker compose up --build

api:
	uv run uvicorn apps.api.main:app --reload --port 8000

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

eval:
	uv run python -m evals.runners.run_demo_eval

seed:
	uv run python -m data.pipeline.build_seed

demo:
	@echo "make demo is built once the bid graph runs end to end (Phase 5)." && exit 1
