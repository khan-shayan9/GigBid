"""Pipeline board, analytics and the memory viewer, from runs and marketplace proposals.

Every figure is counted live from this account's threads and its marketplace proposals; nothing
is estimated.
"""

import math
from collections import Counter

from agent.memory.promotion_rules import promote_outcome
from agent.memory.store import MEMORY_KINDS, OUTCOME, delete_memory, list_memories
from apps.api.errors import ApiError
from apps.api.runtime import Runtime
from apps.api.schemas.app import (
    Analytics,
    CostLatency,
    MemoryItem,
    MemoryList,
    Pipeline,
    PipelineCard,
    RateRow,
    ReasonCount,
)
from apps.api.schemas.runs import RunSummary
from apps.api.services import profiles, runs

STAGES = ("drafted", "submitted", "viewed", "replied", "interview", "hired", "lost")
REPLIED_OR_LATER = {"replied", "interview", "hired"}
TOP_REASONS = 5
SEEN_STATUSES = ("pipeline_statuses",)  # last proposal statuses the worker saw, per account


async def _proposals(rt: Runtime, account: str) -> list[dict]:
    persona = await profiles.persona_of(rt, account)
    async with rt.open_mcp(persona, ["marketplace"]) as mcp:
        return (await mcp.call("web", "list_proposals", {}))["proposals"]


async def pipeline(rt: Runtime, account: str) -> Pipeline:
    bid_runs = {run.subject: run for run in await runs.summaries(rt, account, "bid")}
    cards = [PipelineCard(stage="awaiting_approval", job_id=run.subject, title=run.title,
                          thread_id=run.thread_id)
             for run in bid_runs.values() if run.pending_approval]
    for proposal in await _proposals(rt, account):
        run = bid_runs.get(proposal["job_id"])
        stage = proposal["status"] if proposal["status"] in STAGES else "submitted"
        cards.append(PipelineCard(stage=stage, job_id=proposal["job_id"],
                                  title=run.title if run else proposal["job_id"],
                                  thread_id=run.thread_id if run else None, proposal=proposal))
    return Pipeline(cards=cards)


async def sync_outcomes(rt: Runtime, account: str) -> int:
    """Promote new proposal outcomes to outcome memory (R7); tell open boards of any change.

    Only proposals this account sent from its own bid thread count: accounts on the same persona
    share its marketplace proposals. Returns how many outcomes changed.
    """
    bid_runs = {run.subject: run for run in await runs.summaries(rt, account, "bid")}
    proposals = await _proposals(rt, account)
    statuses = {proposal["job_id"]: proposal["status"] for proposal in proposals}
    seen = await rt.store.aget(SEEN_STATUSES, account)
    if seen is None or seen.value != statuses:  # e.g. "viewed": no memory, but a board change
        await rt.store.aput(SEEN_STATUSES, account, statuses)
        await rt.runs.publish(runs.pipeline_channel(account), {"type": "changed"})
    changed = 0
    for proposal in proposals:
        run = bid_runs.get(proposal["job_id"])
        if run is None or run.approval_status != "approved":
            continue
        known = await rt.store.aget((OUTCOME, account), proposal["job_id"])
        if known and known.value["outcome"] == proposal["status"]:
            continue
        values = await runs.values_of(rt, "bid", run.thread_id)
        skills = (values.get("job_spec") or {}).get("required_skills") or values["job"].get("skills", [])
        cited = (values.get("proposal_draft") or {}).get("evidence_ids", [])
        if await promote_outcome(rt.store, account, proposal["job_id"], proposal["status"],
                                 skills, cited):
            changed += 1
    return changed


def _approval(run: RunSummary) -> str:
    if run.pending_approval:
        return "pending"
    return (run.approval_status or "none").split(":", 1)[0]


async def analytics(rt: Runtime, account: str) -> Analytics:
    bid_runs = await runs.summaries(rt, account, "bid")
    proposals = await _proposals(rt, account)
    by_job = {run.subject: run for run in bid_runs}
    rows: dict[str, Counter] = {}
    for proposal in proposals:
        if proposal["status"] == "drafted":
            continue
        run = by_job.get(proposal["job_id"])
        row = rows.setdefault((run.category if run else None) or "unknown", Counter())
        row["submitted"] += 1
        row["replied"] += proposal["status"] in REPLIED_OR_LATER
        row["hired"] += proposal["status"] == "hired"
    reasons = Counter(run.approval_status.split(":", 1)[1].strip() or "(no reason)"
                      for run in bid_runs
                      if (run.approval_status or "").startswith("rejected"))
    return Analytics(
        jobs_analysed=len(bid_runs),
        decisions=Counter(run.decision or "undecided" for run in bid_runs),
        approvals=Counter(_approval(run) for run in bid_runs),
        needs_attention=sum(bool(run.status) for run in bid_runs),
        rates_by_category=[RateRow(category=category, **counts)
                           for category, counts in sorted(rows.items())],
        connects_spent=sum(p["connects_cost"] for p in proposals if p["status"] != "drafted"),
        outcomes=Counter(proposal["status"] for proposal in proposals),
        top_rejection_reasons=[ReasonCount(reason=reason, count=count)
                               for reason, count in reasons.most_common(TOP_REASONS)],
        cost_and_latency=await _cost_latency(rt, bid_runs))


def _p95(values: list[float]) -> float | None:
    """Nearest-rank 95th percentile."""
    ordered = sorted(values)
    return ordered[max(math.ceil(0.95 * len(ordered)) - 1, 0)] if ordered else None


async def _cost_latency(rt: Runtime, bid_runs: list[RunSummary]) -> CostLatency:
    timed, proposal_seconds, proposal_tokens = [], [], []
    for run in bid_runs:
        seconds = await runs.first_segment_seconds(rt, run.thread_id)
        if seconds is None:
            continue
        timed.append(seconds)
        values = await runs.values_of(rt, "bid", run.thread_id)
        if values.get("proposal_draft"):
            proposal_seconds.append(seconds)
            proposal_tokens.append(values.get("tokens_used", 0))
    p95_tokens = _p95(proposal_tokens)
    return CostLatency(jobs_timed=len(timed), p95_seconds_per_job=_p95(timed),
                       proposals_timed=len(proposal_seconds),
                       p95_seconds_per_proposal=_p95(proposal_seconds),
                       p95_tokens_per_proposal=None if p95_tokens is None else int(p95_tokens))


def _summary(kind: str, item: dict) -> str:
    if kind == "style":
        return (f"Edit style '{item['pattern']}', seen in {item['edit_count']} approved edits. "
                f"Example: {item.get('example', '')}")
    return f"{item['outcome']} on job {item['id']}"


async def memories(rt: Runtime, account: str) -> MemoryList:
    items = [MemoryItem(id=item["id"], kind=kind, summary=_summary(kind, item))
             for kind in MEMORY_KINDS for item in await list_memories(rt.store, kind, account)]
    return MemoryList(items=items)


async def forget(rt: Runtime, account: str, kind: str, item_id: str) -> None:
    if kind not in MEMORY_KINDS:
        raise ApiError(404, "not_found", "No such memory kind.")
    await delete_memory(rt.store, kind, account, item_id)
