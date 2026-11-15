"""SSE bridge: LangGraph's `updates` stream for one thread, as text/event-stream.

The first event is a `snapshot` (the run as the checkpoint has it), then one `node` event per
finished node and `interrupt` when the thread pauses for approval, then `end`. A client that
connects to a thread with nothing running gets the snapshot and `end` straight away.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from apps.api.runtime import Runtime
from apps.api.services import runs

KEEPALIVE_S = 15  # an idle comment line keeps proxies from closing the stream


def _event(name: str, data: Any) -> str:
    return f"event: {name}\ndata: {json.dumps(data, default=str)}\n\n"


async def open_run_stream(rt: Runtime, account: str, thread_id: str) -> AsyncIterator[str]:
    """Check access and read the snapshot now, so a refusal is a normal JSON error response."""
    runs.kind_of(account, thread_id)
    queue: asyncio.Queue = asyncio.Queue()
    listeners = rt.listeners.setdefault(thread_id, [])
    listeners.append(queue)  # before the snapshot, so no event falls in between
    try:
        snapshot = await runs.detail(rt, account, thread_id)
    except Exception:
        _forget(rt, thread_id, queue)
        raise
    return _events(rt, thread_id, queue, snapshot.model_dump(mode="json"))


async def _events(rt: Runtime, thread_id: str, queue: asyncio.Queue,
                  snapshot: dict[str, Any]) -> AsyncIterator[str]:
    try:
        yield _event("snapshot", snapshot)
        if thread_id not in rt.running:
            yield _event("end", {})
            return
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), KEEPALIVE_S)
            except TimeoutError:
                yield ": keepalive\n\n"
                continue
            yield _event(event["type"], event)
            if event == runs.END_EVENT:
                return
    finally:
        _forget(rt, thread_id, queue)


def _forget(rt: Runtime, thread_id: str, queue: asyncio.Queue) -> None:
    listeners = rt.listeners.get(thread_id, [])
    if queue in listeners:
        listeners.remove(queue)
    if not listeners:
        rt.listeners.pop(thread_id, None)
