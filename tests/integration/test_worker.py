"""Worker mode end to end (E1, C6): the Arq worker runs the graph, a pending approval survives an
API restart on Postgres, and the proposal is submitted exactly once even if the job runs again.

Needs Redis and Postgres (REDIS_URL, DATABASE_URL), so it runs in CI only, like the other
Postgres tests. The worker runs in burst mode in this process, with the fake marketplace.
"""

import asyncio
import os
import secrets
import time
from typing import Any

import pytest
from arq.connections import RedisSettings
from arq.worker import Worker
from fastapi.testclient import TestClient

from apps.api.auth.users import hash_password
from apps.api.main import create_app
from apps.api.runtime import open_runtime
from apps.api.services import runs
from tests.e2e.fake_backend import FakeMarket, fake_overrides
from worker.main import WorkerSettings, shutdown, startup

pytestmark = pytest.mark.skipif(
    not (os.environ.get("REDIS_URL") and os.environ.get("DATABASE_URL")),
    reason="needs Redis and Postgres (CI)")
PASSWORD = secrets.token_hex(8)


def run_worker(market: FakeMarket, then: Any = None) -> None:
    """Run every queued job, then `then(runtime)` on the worker's runtime."""
    async def burst() -> None:
        async with open_runtime(**fake_overrides(market)) as rt:
            worker = Worker(WorkerSettings.functions, on_startup=startup, on_shutdown=shutdown,
                            burst=True, handle_signals=False, ctx={"rt": rt},
                            redis_settings=RedisSettings.from_dsn(os.environ["REDIS_URL"]))
            await worker.main()
            await worker.close()
            if then:
                await then(rt)
    asyncio.run(burst())


def api(market: FakeMarket, account: str) -> TestClient:
    client = TestClient(create_app(**fake_overrides(market)))
    client.__enter__()
    assert client.post("/auth/login", json={"username": account, "password": PASSWORD}).is_success
    return client


def wait_for(client: TestClient, thread_id: str, check: Any) -> dict[str, Any]:
    for _ in range(100):
        run = client.get(f"/runs/{thread_id}").json()
        if check(run):
            return run
        time.sleep(0.05)
    raise AssertionError(f"run never reached the expected state: {run}")


def test_worker_runs_survive_an_api_restart_and_submit_once(
        monkeypatch: pytest.MonkeyPatch) -> None:
    account = f"w{secrets.token_hex(4)}"  # fresh threads on a reused database
    monkeypatch.setenv("APP_SECRET_KEY", secrets.token_hex(16))
    monkeypatch.setenv("APP_USERS", f"{account}={hash_password(PASSWORD)}")
    monkeypatch.setenv("API_PERSISTENCE", "postgres")
    monkeypatch.setenv("RUN_MODE", "worker")
    market = FakeMarket()
    thread = f"{account}:bid:job-clinic"

    client = api(market, account)
    assert client.put("/profile", json={"persona": "ai_ml_engineer"}).is_success
    assert client.post("/jobs/job-clinic/analyse").json()["thread_id"] == thread
    assert client.get(f"/runs/{thread}").json()["running"]  # queued, not run by the API
    run_worker(market)
    assert wait_for(client, thread, lambda run: not run["running"])["pending_approval"]
    client.__exit__(None, None, None)  # the API restarts

    client = api(market, account)
    assert client.get(f"/runs/{thread}").json()["pending_approval"]
    assert client.post(f"/runs/{thread}/resume", json={"action": "approve"}).status_code == 202

    async def replay(rt: Any) -> None:  # the same resume job delivered a second time
        await runs.run_segment(rt, account, "ai_ml_engineer", thread, "bid",
                               answer={"action": "approve"})
    run_worker(market, then=replay)
    done = wait_for(client, thread, lambda run: not run["running"])
    assert done["approval_status"] == "approved"
    assert len([call for call in market.tools("submit_proposal")
                if not call["dry_run"]]) == 1
    client.__exit__(None, None, None)
