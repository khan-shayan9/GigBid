"""Inbox service: scouted jobs ranked by fit, skipping, and starting a bid run for a job."""

from agent.config import load_config
from agent.nodes.scout import scout_jobs
from apps.api.runtime import Runtime
from apps.api.schemas.app import Inbox, InboxItem
from apps.api.schemas.runs import RunRef
from apps.api.services import profiles, runs

SKIPS = "inbox_skips"


async def inbox(rt: Runtime, account: str) -> Inbox:
    profile = await profiles.get_profile(rt, account)
    persona = await profiles.persona_of(rt, account)
    async with rt.open_mcp(persona, ["marketplace"]) as mcp:
        jobs = await scout_jobs(mcp, profile.saved_searches, load_config()["api"]["inbox_limit"])
    skipped = {item.key for item in await rt.store.asearch((SKIPS, account), limit=1000)}
    analysed = {run.subject: run for run in await runs.summaries(rt, account, "bid")}
    items = []
    for job in jobs:
        run = analysed.get(job["job_id"])
        if job["job_id"] in skipped:
            continue
        if profile.autonomy == "auto_skip_low_fit" and run and run.decision == "skip":
            continue  # the only automatic action allowed: hiding a job the agent would skip
        items.append(InboxItem(job=job, run=run))
    # Analysed jobs first, best fit first; then the rest, newest first (scout's order).
    items.sort(key=lambda item: -(item.run.fit_score or 0) if item.run else 1)
    return Inbox(items=items)


async def skip(rt: Runtime, account: str, job_id: str) -> None:
    await rt.store.aput((SKIPS, account), job_id, {"skipped": True})


async def analyse(rt: Runtime, account: str, job_id: str) -> RunRef:
    persona = await profiles.persona_of(rt, account)
    async with rt.open_mcp(persona, ["marketplace"]) as mcp:
        job = await mcp.call("web", "get_job", {"job_id": job_id})
    return await runs.start(rt, account, persona, "bid", job_id, {"job": job})
