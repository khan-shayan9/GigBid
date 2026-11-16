"""Which threads are running, why a run failed, and its live events: in process or in Redis.

`LocalRunState` keeps them in this process (graph segments run as API tasks: local dev, tests).
`RedisRunState` keeps them in Redis, so the API and the Arq worker (worker/main.py) share them:
a running flag with an expiry (a dead worker cannot leave a run "running" forever), a failure
note, and one pub/sub channel per thread for the SSE bridge.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

PREFIX = "gigbid"


class LocalRunState:
    def __init__(self) -> None:
        self.running: dict[str, asyncio.Task | None] = {}
        self.listeners: dict[str, list[asyncio.Queue]] = {}
        self.failures: dict[str, str] = {}

    async def claim(self, thread_id: str) -> bool:
        if thread_id in self.running:
            return False
        self.running[thread_id] = None
        return True

    async def touch(self, thread_id: str) -> None:
        pass

    async def release(self, thread_id: str) -> None:
        self.running.pop(thread_id, None)

    async def is_running(self, thread_id: str) -> bool:
        return thread_id in self.running

    async def set_failure(self, thread_id: str, message: str | None) -> None:
        if message is None:
            self.failures.pop(thread_id, None)
        else:
            self.failures[thread_id] = message

    async def failure(self, thread_id: str) -> str | None:
        return self.failures.get(thread_id)

    async def publish(self, thread_id: str, event: dict[str, Any]) -> None:
        for queue in self.listeners.get(thread_id, []):
            queue.put_nowait(event)

    @asynccontextmanager
    async def listen(self, thread_id: str) -> AsyncIterator[Any]:
        queue: asyncio.Queue = asyncio.Queue()
        listeners = self.listeners.setdefault(thread_id, [])
        listeners.append(queue)
        try:
            yield _QueueEvents(queue)
        finally:
            listeners.remove(queue)
            if not listeners:
                self.listeners.pop(thread_id, None)

    def cancel_all(self) -> None:
        for task in self.running.values():
            if task is not None:
                task.cancel()


class _QueueEvents:
    def __init__(self, queue: asyncio.Queue) -> None:
        self.queue = queue

    async def get(self, timeout: float) -> dict[str, Any] | None:
        """The next event, or None after `timeout` seconds without one."""
        try:
            return await asyncio.wait_for(self.queue.get(), timeout)
        except TimeoutError:
            return None


class _PubSubEvents:
    def __init__(self, pubsub: Any) -> None:
        self.pubsub = pubsub

    async def get(self, timeout: float) -> dict[str, Any] | None:
        """The next event, or None after `timeout` seconds (never cancels a pending read)."""
        deadline = asyncio.get_running_loop().time() + timeout
        while (left := deadline - asyncio.get_running_loop().time()) > 0:
            message = await self.pubsub.get_message(ignore_subscribe_messages=True,
                                                    timeout=left)
            if message and message["type"] == "message":
                return json.loads(message["data"])
        return None


class RedisRunState:
    def __init__(self, redis: Any, running_ttl_s: int) -> None:
        self.redis, self.ttl = redis, running_ttl_s

    @staticmethod
    def _key(kind: str, thread_id: str) -> str:
        return f"{PREFIX}:{kind}:{thread_id}"

    async def claim(self, thread_id: str) -> bool:
        return bool(await self.redis.set(self._key("running", thread_id), 1, nx=True,
                                         ex=self.ttl))

    async def touch(self, thread_id: str) -> None:
        await self.redis.set(self._key("running", thread_id), 1, ex=self.ttl)

    async def release(self, thread_id: str) -> None:
        await self.redis.delete(self._key("running", thread_id))

    async def is_running(self, thread_id: str) -> bool:
        return bool(await self.redis.exists(self._key("running", thread_id)))

    async def set_failure(self, thread_id: str, message: str | None) -> None:
        if message is None:
            await self.redis.delete(self._key("failure", thread_id))
        else:
            await self.redis.set(self._key("failure", thread_id), message, ex=7 * 24 * 3600)

    async def failure(self, thread_id: str) -> str | None:
        value = await self.redis.get(self._key("failure", thread_id))
        return value.decode() if isinstance(value, bytes) else value

    async def publish(self, thread_id: str, event: dict[str, Any]) -> None:
        await self.redis.publish(self._key("events", thread_id), json.dumps(event, default=str))

    @asynccontextmanager
    async def listen(self, thread_id: str) -> AsyncIterator[Any]:
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self._key("events", thread_id))
        try:
            yield _PubSubEvents(pubsub)
        finally:
            await pubsub.unsubscribe()
            await pubsub.aclose()
