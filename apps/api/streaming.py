"""SSE bridge: LangGraph's `updates` stream for one thread, as text/event-stream.

The first event is a `snapshot` (the run as the checkpoint has it), then one `node` event per
finished node and `interrupt` when the thread pauses for approval, then `end`. A client that
connects to a thread with nothing running gets the snapshot and `end` straight away.
"""

import json
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Any

from apps.api.runtime import Runtime
from apps.api.services import runs

KEEPALIVE_S = 15  # an idle comment line keeps proxies from closing the stream


def _event(name: str, data: Any) -> str:
    return f"event: {name}\ndata: {json.dumps(data, default=str)}\n\n"


async def open_run_stream(rt: Runtime, account: str, thread_id: str) -> AsyncIterator[str]:
    """Check access and read the snapshot now, so a refusal is a normal JSON error response."""
    runs.kind_of(account, thread_id)
    stack = AsyncExitStack()
    # Listen before reading the snapshot, so no event falls in between.
    events = await stack.enter_async_context(rt.runs.listen(thread_id))
    try:
        snapshot = await runs.detail(rt, account, thread_id)
    except Exception:
        await stack.aclose()
        raise
    return _events(rt, thread_id, stack, events, snapshot.model_dump(mode="json"))


async def open_pipeline_stream(rt: Runtime, account: str) -> AsyncIterator[str]:
    """`ready`, then `changed` whenever a run ends or a proposal outcome arrives."""
    stack = AsyncExitStack()
    events = await stack.enter_async_context(rt.runs.listen(runs.pipeline_channel(account)))
    return _pipeline_events(stack, events)


async def _pipeline_events(stack: AsyncExitStack, events: Any) -> AsyncIterator[str]:
    async with stack:
        yield _event("ready", {})
        while True:
            event = await events.get(KEEPALIVE_S)
            yield ": keepalive\n\n" if event is None else _event(event["type"], event)


async def _events(rt: Runtime, thread_id: str, stack: AsyncExitStack, events: Any,
                  snapshot: dict[str, Any]) -> AsyncIterator[str]:
    async with stack:
        yield _event("snapshot", snapshot)
        if not snapshot["running"]:
            yield _event("end", {})
            return
        while True:
            event = await events.get(KEEPALIVE_S)
            if event is None:
                if not await rt.runs.is_running(thread_id):  # e.g. its worker died
                    yield _event("end", {})
                    return
                yield ": keepalive\n\n"
                continue
            yield _event(event["type"], event)
            if event == runs.END_EVENT:
                return
