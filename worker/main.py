"""Arq worker (E1): graph segments the API hands over, scheduled scouting and outcome sync.

Run with `arq worker.main.WorkerSettings` (compose service `worker`). It shares the API's
settings: RUN_MODE=worker, API_PERSISTENCE=postgres, DATABASE_URL and REDIS_URL.

Idempotent processing: a graph segment decides what to run from its checkpoint
(apps/api/services/runs.run_segment), so a job retried after a crash never replays an approval,
and every marketplace write carries an idempotency key (agent/idempotency.py).
"""

import logging
import os
from contextlib import AsyncExitStack
from typing import Any

from arq import cron, func
from arq.connections import RedisSettings

from apps.api.runtime import Runtime, open_runtime, worker_settings
from apps.api.services import insights, jobs, runs
from data.pipeline.pii import mask_pii

log = logging.getLogger("gigbid.worker")
SETTINGS = worker_settings()


async def startup(ctx: dict[str, Any]) -> None:
    stack = AsyncExitStack()
    ctx["stack"] = stack
    if "rt" not in ctx:  # tests put their own runtime in ctx
        ctx["rt"] = await stack.enter_async_context(open_runtime())


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["stack"].aclose()


async def run_segment(ctx: dict[str, Any], account: str, persona: str, thread_id: str,
                      kind: runs.RunKind, graph_input: dict[str, Any] | None,
                      answer: dict[str, Any] | None, replay_from: str | None = None) -> None:
    rt: Runtime = ctx["rt"]
    await rt.runs.touch(thread_id)  # a retried job marks its run as running again
    await runs.run_segment(rt, account, persona, thread_id, kind, graph_input, answer,
                           replay_from)


async def scout(ctx: dict[str, Any]) -> dict[str, int]:
    """Start bid runs for new jobs from every account's saved searches."""
    rt: Runtime = ctx["rt"]
    started = {}
    for account in await jobs.accounts(rt):
        try:
            started[account] = await jobs.queue_new_jobs(
                rt, account, SETTINGS["scout_new_runs_per_account"])
        except Exception as error:  # noqa: BLE001 - one account's failure must not stop others
            log.error("scout for %s failed: %s", account, mask_pii(repr(error)))
    return started


async def sync_outcomes(ctx: dict[str, Any]) -> dict[str, int]:
    """Promote proposal outcomes (replied, interview, hired, lost) to outcome memory."""
    rt: Runtime = ctx["rt"]
    changed = {}
    for account in await jobs.accounts(rt):
        try:
            changed[account] = await insights.sync_outcomes(rt, account)
        except Exception as error:  # noqa: BLE001 - the marketplace may be down; retry next time
            log.error("outcome sync for %s failed: %s", account, mask_pii(repr(error)))
    return changed


class WorkerSettings:
    # keep_result=0: a finished job leaves no result key, so the thread can queue its next one.
    functions = (func(run_segment, timeout=SETTINGS["job_timeout_s"], keep_result=0,
                      max_tries=SETTINGS["max_tries"]),)
    max_jobs = SETTINGS["max_jobs"]
    cron_jobs = (
        cron(scout, hour=set(SETTINGS["scout_hours"]), minute=0,
             timeout=SETTINGS["job_timeout_s"]),
        cron(sync_outcomes, minute=set(range(0, 60, SETTINGS["outcome_sync_minutes"]))),
    )
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379"))
