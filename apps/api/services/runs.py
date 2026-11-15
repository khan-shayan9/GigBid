"""Run service: start, resume and read bid and conversation graph threads.

A thread id is `<account>:<kind>:<subject>` (kind `bid` with a job id, `conv` with a client
message id), so every read checks the account prefix (tenant scoping). The checkpoint is the
truth: pending approvals and the run timeline are read back from it, so a refresh or a dropped
stream loses nothing. The live progress events are only a view (apps/api/streaming.py).
shortcut: graph segments run as tasks inside the API process; the Phase 7 Arq worker runs them.
"""

import asyncio
import logging
from typing import Any

from langgraph.types import Command

from agent.nodes.writer import rewrite_paragraph
from apps.api.errors import ApiError
from apps.api.runtime import Runtime
from apps.api.schemas.runs import (
    Preview,
    ResumeIn,
    RunDetail,
    RunKind,
    RunRef,
    RunSummary,
    TimelineStep,
)
from data.pipeline.pii import mask_pii

log = logging.getLogger("gigbid.api")
KIND_PREFIX: dict[RunKind, str] = {"bid": "bid", "conversation": "conv"}
SERVERS: dict[RunKind, list[str]] = {"bid": ["portfolio", "marketplace"],
                                     "conversation": ["marketplace", "workspace"]}
END_EVENT = {"type": "end"}
RUN_FAILED = "The run stopped before finishing. Retry it."


def thread_id_for(account: str, kind: RunKind, subject: str) -> str:
    return f"{account}:{KIND_PREFIX[kind]}:{subject}"


def kind_of(account: str, thread_id: str) -> RunKind:
    """The thread's kind, after checking that it belongs to `account`."""
    owner, _, rest = thread_id.partition(":")
    if owner != account:
        raise ApiError(403, "forbidden", "This run belongs to another account.")
    prefix = rest.partition(":")[0]
    for kind, known in KIND_PREFIX.items():
        if prefix == known:
            return kind
    raise ApiError(404, "not_found", "No such run.")


def _graph(rt: Runtime, kind: RunKind) -> Any:
    return rt.bid_graph if kind == "bid" else rt.conversation_graph


def _config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def publish(rt: Runtime, thread_id: str, event: dict[str, Any]) -> None:
    for queue in rt.listeners.get(thread_id, []):
        queue.put_nowait(event)


def _launch(rt: Runtime, account: str, persona: str, thread_id: str, kind: RunKind,
            graph_input: Any) -> None:
    """Run one graph segment (to the next interrupt or the end) in the background."""
    async def run() -> None:
        try:
            async with rt.open_mcp(persona, SERVERS[kind]) as mcp:
                config = {"configurable": {"mcp": mcp, "model": rt.model_for(kind),
                                           "thread_id": thread_id, "user_id": account},
                          "metadata": {"account": account, "kind": kind}}
                async for chunk in _graph(rt, kind).astream(graph_input, config,
                                                            stream_mode="updates"):
                    for node in chunk:
                        event = "interrupt" if node == "__interrupt__" else "node"
                        publish(rt, thread_id, {"type": event, "node": node})
        except Exception as error:  # noqa: BLE001 - the thread keeps its last checkpoint
            log.error("run %s stopped: %s", thread_id, mask_pii(repr(error)))
            rt.failures[thread_id] = RUN_FAILED
            publish(rt, thread_id, {"type": "error", "message": RUN_FAILED})
        finally:
            rt.running.pop(thread_id, None)
            publish(rt, thread_id, END_EVENT)

    rt.failures.pop(thread_id, None)
    rt.running[thread_id] = asyncio.create_task(run())


def _claim(rt: Runtime, thread_id: str) -> None:
    """Reserve the thread before any await, so two clicks cannot run it twice."""
    if thread_id in rt.running:
        raise ApiError(409, "run_in_progress", "This run is still working.")
    rt.running[thread_id] = None


async def start(rt: Runtime, account: str, persona: str, kind: RunKind, subject: str,
                graph_input: dict[str, Any]) -> RunRef:
    """Start a thread once; asking again for the same job or message returns the same thread."""
    thread_id = thread_id_for(account, kind, subject)
    if thread_id in rt.running:
        return RunRef(thread_id=thread_id)
    _claim(rt, thread_id)
    try:
        existing = await _graph(rt, kind).aget_state(_config(thread_id))
    except Exception:
        rt.running.pop(thread_id, None)
        raise
    if existing.values:
        rt.running.pop(thread_id, None)
        return RunRef(thread_id=thread_id)
    _launch(rt, account, persona, thread_id, kind, graph_input)
    return RunRef(thread_id=thread_id)


async def resume(rt: Runtime, account: str, persona: str, thread_id: str,
                 answer: ResumeIn) -> RunRef:
    kind = kind_of(account, thread_id)
    text_field = "cover_letter" if kind == "bid" else "reply"
    if answer.action == "edit" and not getattr(answer, text_field):
        raise ApiError(422, "invalid_edit", f"An edit needs the edited {text_field}.")
    _claim(rt, thread_id)
    try:
        state = await _graph(rt, kind).aget_state(_config(thread_id))
    except Exception:
        rt.running.pop(thread_id, None)
        raise
    if not state.interrupts:
        rt.running.pop(thread_id, None)
        raise ApiError(409, "no_pending_approval", "Nothing is waiting for approval here.")
    _launch(rt, account, persona, thread_id, kind,
            Command(resume=answer.model_dump(exclude_none=True)))
    return RunRef(thread_id=thread_id)


async def retry(rt: Runtime, account: str, persona: str, thread_id: str) -> RunRef:
    """Continue a run that stopped on an error (e.g. the marketplace was down while sending)."""
    kind = kind_of(account, thread_id)
    _claim(rt, thread_id)
    try:
        state = await _graph(rt, kind).aget_state(_config(thread_id))
    except Exception:
        rt.running.pop(thread_id, None)
        raise
    if state.interrupts or not state.next:
        rt.running.pop(thread_id, None)
        raise ApiError(409, "nothing_to_retry", "This run is not stopped on an error.")
    _launch(rt, account, persona, thread_id, kind, None)
    return RunRef(thread_id=thread_id)


async def detail(rt: Runtime, account: str, thread_id: str) -> RunDetail:
    kind = kind_of(account, thread_id)
    graph = _graph(rt, kind)
    state = await graph.aget_state(_config(thread_id))
    running = thread_id in rt.running
    if not state.values and not running:
        if thread_id in rt.failures:  # failed before its first checkpoint: say so, not "missing"
            raise ApiError(502, "run_failed", rt.failures[thread_id])
        raise ApiError(404, "not_found", "No such run.")
    history = [snapshot async for snapshot in graph.aget_state_history(_config(thread_id))]
    timeline = [TimelineStep(step=snapshot.metadata.get("step", 0),
                             nodes=[task.name for task in snapshot.tasks],
                             at=snapshot.created_at)
                for snapshot in reversed(history[1:]) if snapshot.tasks]
    values = state.values
    preview = values.get("preview")
    return RunDetail(
        thread_id=thread_id, kind=kind, running=running,
        pending_approval=bool(state.interrupts) and not running,
        status=values.get("status"), errors=values.get("errors", []),
        steps=values.get("steps", 0), tokens_used=values.get("tokens_used", 0),
        timeline=timeline, approval_status=values.get("approval_status"),
        job=values.get("job"), job_spec=values.get("job_spec"),
        risk_report=values.get("risk_report"), fit_report=values.get("fit_report"),
        decision=values.get("decision"), price_quote=values.get("price_quote"),
        draft=values.get("proposal_draft"), evidence=values.get("evidence", []),
        claims=values.get("claim_verification", []), critique=values.get("critique"),
        compliance=values.get("compliance_verdict"), revisions=values.get("revisions", 0),
        preview=(Preview(unavailable=preview["unavailable"]) if "unavailable" in preview
                 else Preview(proposal=preview)) if preview else None,
        submission=values.get("submission"), client_message=values.get("message"),
        intent=values.get("intent"), reply=values.get("reply"), slots=values.get("slots", []),
        sent=values.get("sent"))


async def summaries(rt: Runtime, account: str, kind: RunKind) -> list[RunSummary]:
    """One account's threads of one kind, newest first.

    shortcut: scans the account's checkpoints; add a runs table if accounts get thousands.
    """
    seen: dict[str, Any] = {}
    async for checkpoint in rt.checkpointer.alist(None, filter={"account": account,
                                                                "kind": kind}):
        seen.setdefault(checkpoint.config["configurable"]["thread_id"], None)
    found = [await _summary(rt, kind, thread_id) for thread_id in seen]
    return sorted(found, key=lambda run: str(run.updated_at or ""), reverse=True)


async def _summary(rt: Runtime, kind: RunKind, thread_id: str) -> RunSummary:
    state = await _graph(rt, kind).aget_state(_config(thread_id))
    values, running = state.values, thread_id in rt.running
    subject = thread_id.split(":", 2)[2]
    job = values.get("job", {})
    risk, fit = values.get("risk_report") or {}, values.get("fit_report") or {}
    return RunSummary(
        thread_id=thread_id, kind=kind, subject=subject,
        title=job.get("title") or values.get("message", subject)[:80],
        category=(job.get("skills") or [None])[0], running=running,
        pending_approval=bool(state.interrupts) and not running, status=values.get("status"),
        approval_status=values.get("approval_status"),
        decision=(values.get("decision") or {}).get("decision"),
        fit_score=fit.get("score"), risk_score=risk.get("score"),
        risk_flags=risk.get("flags", []), price=values.get("price_quote"),
        updated_at=state.created_at)


async def regenerate(rt: Runtime, account: str, thread_id: str, paragraph: str) -> str:
    if kind_of(account, thread_id) != "bid":
        raise ApiError(400, "not_a_proposal", "Only proposal drafts have paragraphs to rewrite.")
    values = (await rt.bid_graph.aget_state(_config(thread_id))).values
    if not values.get("proposal_draft"):
        raise ApiError(409, "no_draft", "This run has no draft yet.")
    evidence = {item["id"]: item for item in values.get("evidence", [])}
    return await rewrite_paragraph(values["job"], evidence, paragraph, rt.model_for("paragraph"))
