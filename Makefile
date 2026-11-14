.PHONY: install dev api test lint eval seed demo

install:
	uv sync --frozen

dev:
	docker compose up --build

api:
	uv run uvicorn apps.api.main:app --reload --port 8000

test:
	uv run pytest -q

lint:
	uv run ruff check .

eval:
	uv run python -m evals.runners.run_demo_eval

seed:
	@echo "make seed is built in Phase 1 (data pipeline)." && exit 1

demo:
	@echo "make demo is built once the bid graph runs end to end (Phase 5)." && exit 1
