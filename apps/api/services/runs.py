"""Run service: start, resume and read bid and conversation graph threads.

A thread id is `<account>:<kind>:<subject>` (kind `bid` with a job id, `conv` with a client
message id), so every read checks the account prefix (tenant scoping). The checkpoint is the
truth: pending approvals and the run timeline are read back from it, so a refresh or a dropped
stream loses nothing. The live progress events are only a view (apps/api/streaming.py).
A graph segment runs in the Arq worker (worker/main.py) in worker mode, else as an API task.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from langgraph.types import Command

from agent import tracing
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
DEAD_LETTER = "dead_letter"  # a node failed after its retries (agent/graphs/guard.py)
ENQUEUE_RETRY_S = 0.5


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


def pipeline_channel(account: str) -> str:
    """Event channel that tells an open pipeline board to reload."""
    return f"pipeline:{account}"


async def values_of(rt: Runtime, kind: RunKind, thread_id: str) -> dict[str, Any]:
    return (await _graph(rt, kind).aget_state(_config(thread_id))).values


async def run_segment(rt: Runtime, account: str, persona: str, thread_id: str, kind: RunKind,
                      graph_input: dict[str, Any] | None = None,
                      answer: dict[str, Any] | None = None,
                      replay_from: str | None = None) -> None:
    """Run one graph segment, to the next interrupt or the end, publishing progress.

    Safe to run twice (an Arq retry after a worker crash): what to run comes from the checkpoint,
    so an approval already consumed is never replayed and a finished thread is left alone.
    `replay_from` re-runs a dead-lettered thread from the checkpoint before its failure.
    """
    try:
        state = await _graph(rt, kind).aget_state(_config(thread_id))
        replay = replay_from is not None and state.values.get("status") == DEAD_LETTER
        if not state.values:
            segment_input: Any = graph_input
        elif state.interrupts:
            segment_input = Command(resume=answer) if answer else None
        else:
            segment_input = None
        if replay or segment_input is not None or (state.next and not state.interrupts):
            async with rt.open_mcp(persona, SERVERS[kind]) as mcp:
                configurable = {"mcp": tracing.traced(mcp), "model": rt.model_for(kind),
                                "thread_id": thread_id, "user_id": account}
                if replay:  # LangGraph forks the thread from that checkpoint
                    configurable["checkpoint_id"] = replay_from
                config = {"configurable": configurable,
                          "metadata": {"account": account, "kind": kind,
                                       "langfuse_session_id": thread_id,
                                       "langfuse_user_id": account},
                          "callbacks": tracing.callbacks(thread_id), "run_name": f"{kind} run"}
                async for chunk in _graph(rt, kind).astream(segment_input, config,
                                                            stream_mode="updates"):
                    await rt.runs.touch(thread_id)
                    for node in chunk:
                        event = "interrupt" if node == "__interrupt__" else "node"
                        await rt.runs.publish(thread_id, {"type": event, "node": node})
    except Exception as error:  # noqa: BLE001 - the thread keeps its last checkpoint
        log.error("run %s (trace %s) stopped: %s", thread_id, tracing.trace_id_for(thread_id),
                  mask_pii(repr(error)))
        await rt.runs.set_failure(thread_id, RUN_FAILED)
        await rt.runs.publish(thread_id, {"type": "error", "message": RUN_FAILED})
    finally:
        await rt.runs.release(thread_id)
        await rt.runs.publish(thread_id, END_EVENT)
        await rt.runs.publish(pipeline_channel(account), {"type": "changed"})


async def _launch(rt: Runtime, account: str, persona: str, thread_id: str, kind: RunKind,
                  graph_input: dict[str, Any] | None = None,
                  answer: dict[str, Any] | None = None,
                  replay_from: str | None = None) -> None:
    """Hand a claimed thread's next segment to the worker, or run it as a task here."""
    try:
        await rt.runs.set_failure(thread_id, None)
        job = None
        if rt.queue is not None:
            # One job id per thread: a thread never has two segments queued or running.
            for attempt in range(2):
                job = await rt.queue.enqueue_job("run_segment", account, persona, thread_id,
                                                 kind, graph_input, answer, replay_from,
                                                 _job_id=f"run:{thread_id}")
                if job is not None or attempt:
                    break
                await asyncio.sleep(ENQUEUE_RETRY_S)  # the last job ends, then Arq drops its key
    except Exception:
        await rt.runs.release(thread_id)
        raise
    if rt.queue is not None:
        if job is None:  # its earlier job is still queued or running; that job owns the flag
            raise ApiError(409, "run_in_progress", "This run is still working.")
        return
    rt.runs.running[thread_id] = asyncio.create_task(
        run_segment(rt, account, persona, thread_id, kind, graph_input, answer, replay_from))


async def _claim(rt: Runtime, thread_id: str) -> None:
    """Reserve the thread before any other await, so two clicks cannot run it twice."""
    if not await rt.runs.claim(thread_id):
        raise ApiError(409, "run_in_progress", "This run is still working.")


async def _state_or_release(rt: Runtime, kind: RunKind, thread_id: str) -> Any:
    try:
        return await _graph(rt, kind).aget_state(_config(thread_id))
    except Exception:
        await rt.runs.release(thread_id)
        raise


async def start(rt: Runtime, account: str, persona: str, kind: RunKind, subject: str,
                graph_input: dict[str, Any]) -> RunRef:
    """Start a thread once; asking again for the same job or message returns the same thread."""
    thread_id = thread_id_for(account, kind, subject)
    if not await rt.runs.claim(thread_id):
        return RunRef(thread_id=thread_id)
    if (await _state_or_release(rt, kind, thread_id)).values:
        await rt.runs.release(thread_id)
        return RunRef(thread_id=thread_id)
    await _launch(rt, account, persona, thread_id, kind, graph_input=graph_input)
    return RunRef(thread_id=thread_id)


async def resume(rt: Runtime, account: str, persona: str, thread_id: str,
                 answer: ResumeIn) -> RunRef:
    kind = kind_of(account, thread_id)
    text_field = "cover_letter" if kind == "bid" else "reply"
    if answer.action == "edit" and not getattr(answer, text_field):
        raise ApiError(422, "invalid_edit", f"An edit needs the edited {text_field}.")
    await _claim(rt, thread_id)
    state = await _state_or_release(rt, kind, thread_id)
    if not state.interrupts:
        await rt.runs.release(thread_id)
        raise ApiError(409, "no_pending_approval", "Nothing is waiting for approval here.")
    await _launch(rt, account, persona, thread_id, kind,
                  answer=answer.model_dump(exclude_none=True))
    return RunRef(thread_id=thread_id)


async def retry(rt: Runtime, account: str, persona: str, thread_id: str) -> RunRef:
    """Continue a run that stopped on an error: one that crashed mid-step (it continues), or one
    dead-lettered after a node's retries, e.g. a model rate limit (it replays from the
    checkpoint before the failing step)."""
    kind = kind_of(account, thread_id)
    await _claim(rt, thread_id)
    state = await _state_or_release(rt, kind, thread_id)
    replay_from = None
    if not state.interrupts and not state.next and state.values.get("status") == DEAD_LETTER:
        replay_from = await _before_failure(rt, kind, thread_id)
    if state.interrupts or not (state.next or replay_from):
        await rt.runs.release(thread_id)
        raise ApiError(409, "nothing_to_retry", "This run is not stopped on an error.")
    await _launch(rt, account, persona, thread_id, kind, replay_from=replay_from)
    return RunRef(thread_id=thread_id)


async def _before_failure(rt: Runtime, kind: RunKind, thread_id: str) -> str | None:
    """The newest checkpoint that still had work to do and no failure status."""
    async for snapshot in _graph(rt, kind).aget_state_history(_config(thread_id)):
        if snapshot.next and not snapshot.values.get("status"):
            return snapshot.config["configurable"]["checkpoint_id"]
    return None


async def detail(rt: Runtime, account: str, thread_id: str) -> RunDetail:
    kind = kind_of(account, thread_id)
    graph = _graph(rt, kind)
    state = await graph.aget_state(_config(thread_id))
    running = await rt.runs.is_running(thread_id)
    if not state.values and not running:
        failure = await rt.runs.failure(thread_id)
        if failure:  # failed before its first checkpoint: say so, not "missing"
            raise ApiError(502, "run_failed", failure)
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
        trace_url=await tracing.trace_url(thread_id),
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
    values, running = state.values, await rt.runs.is_running(thread_id)
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


async def first_segment_seconds(rt: Runtime, thread_id: str) -> float | None:
    """Seconds from a bid thread's first checkpoint to its first pause or end (one job analysed);
    None while it is still in its first segment."""
    history = [snapshot async for snapshot in
               rt.bid_graph.aget_state_history(_config(thread_id))][::-1]
    for snapshot in history:
        if snapshot.interrupts or not snapshot.next:
            started = datetime.fromisoformat(history[0].created_at)
            return (datetime.fromisoformat(snapshot.created_at) - started).total_seconds()
    return None


async def regenerate(rt: Runtime, account: str, thread_id: str, paragraph: str) -> str:
    if kind_of(account, thread_id) != "bid":
        raise ApiError(400, "not_a_proposal", "Only proposal drafts have paragraphs to rewrite.")
    values = (await rt.bid_graph.aget_state(_config(thread_id))).values
    if not values.get("proposal_draft"):
        raise ApiError(409, "no_draft", "This run has no draft yet.")
    evidence = {item["id"]: item for item in values.get("evidence", [])}
    return await rewrite_paragraph(values["job"], evidence, paragraph, rt.model_for("paragraph"))
