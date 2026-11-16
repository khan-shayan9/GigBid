# Worker

Arq worker (`worker/main.py`): runs graph segments the API hands over (`RUN_MODE=worker`),
scouts saved searches on a schedule, and promotes proposal outcomes to memory.
Run: `uv run arq worker.main.WorkerSettings`. See `docs/RUNBOOK.md`.
