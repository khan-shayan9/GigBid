"""Pipeline board, analytics and the memory viewer, from runs and marketplace proposals.

Every figure is counted live from this account's threads and its marketplace proposals; nothing
is estimated.
"""

from collections import Counter

from agent.memory.store import MEMORY_KINDS, delete_memory, list_memories
from apps.api.errors import ApiError
from apps.api.runtime import Runtime
from apps.api.schemas.app import (
    Analytics,
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
NOT_MEASURED = ("Cost and latency per proposal come from Langfuse tracing, added in Phase 7; "
                "they are not measured yet.")


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
        cost_and_latency=NOT_MEASURED)


def _summary(kind: str, item: dict) -> str:
    if kind == "style":
        return (f"Edit style '{item['pattern']}', seen in {item['edit_count']} approved edits. "
                f"Example: {item.get('example', '')}")
    return f"{item.get('event', 'outcome')} on job {item['id']}"


async def memories(rt: Runtime, account: str) -> MemoryList:
    items = [MemoryItem(id=item["id"], kind=kind, summary=_summary(kind, item))
             for kind in MEMORY_KINDS for item in await list_memories(rt.store, kind, account)]
    return MemoryList(items=items)


async def forget(rt: Runtime, account: str, kind: str, item_id: str) -> None:
    if kind not in MEMORY_KINDS:
        raise ApiError(404, "not_found", "No such memory kind.")
    await delete_memory(rt.store, kind, account, item_id)
