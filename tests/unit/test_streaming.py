"""The SSE bridge ends a stream whose run stopped without an `end` event (its worker died)."""

from contextlib import AsyncExitStack
from typing import Any

from apps.api import streaming


class Silent:
    async def get(self, timeout: float) -> None:
        return None  # no event before the keepalive timeout


class DeadRuns:
    async def is_running(self, thread_id: str) -> bool:
        return False


class Rt:
    runs = DeadRuns()


async def test_a_stream_ends_when_its_run_is_no_longer_running() -> None:
    rt: Any = Rt()
    events = [chunk async for chunk in streaming._events(rt, "a:bid:j", AsyncExitStack(),
                                                         Silent(), {"running": True})]
    assert [chunk.split("\n")[0] for chunk in events] == ["event: snapshot", "event: end"]
