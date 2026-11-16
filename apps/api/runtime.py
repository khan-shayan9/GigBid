"""What the API's services share for the app's lifetime: persistence, graphs, MCP and models.

The checkpointer and store are Postgres when API_PERSISTENCE=postgres (docker compose, deploy),
else in memory (local dev and tests). RUN_MODE=worker (compose, deploy) hands graph segments to
the Arq worker through Redis and needs Postgres; `inline` runs them as tasks in this process.
`open_mcp` and `model_for` are injectable, so end-to-end tests run the real API against a fake
marketplace and a scripted model (tests/e2e/).
"""

import os
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from agent import tracing
from agent.config import load_config
from agent.graphs.bid_graph import build_bid_graph
from agent.graphs.conversation_graph import build_conversation_graph
from agent.llm import chat_model
from agent.mcp_client import McpClient
from apps.api.run_state import LocalRunState, RedisRunState

OpenMcp = Callable[[str, list[str]], AbstractAsyncContextManager[Any]]


def _default_open_mcp(persona: str, servers: list[str]) -> AbstractAsyncContextManager[Any]:
    return McpClient(persona, servers=servers)


def _default_model_for(kind: str) -> Any:
    return chat_model(load_config()["api"]["run_models"][kind])


@dataclass
class Runtime:
    checkpointer: Any
    store: Any
    open_mcp: OpenMcp = _default_open_mcp
    model_for: Callable[[str], Any] = _default_model_for
    # Running flags, failure notes and live events (apps/api/run_state.py).
    runs: LocalRunState | RedisRunState = field(default_factory=LocalRunState)
    # The Arq pool in worker mode; None runs segments as tasks in this process.
    queue: Any = None
    bid_graph: Any = None
    conversation_graph: Any = None

    def __post_init__(self) -> None:
        self.bid_graph = build_bid_graph(self.checkpointer, self.store)
        self.conversation_graph = build_conversation_graph(self.checkpointer)


@asynccontextmanager
async def open_runtime(**overrides: Any) -> AsyncIterator[Runtime]:
    persistence = os.environ.get("API_PERSISTENCE") or load_config()["api"]["persistence"]
    async with AsyncExitStack() as stack:
        if persistence == "postgres":
            from langgraph.store.postgres.aio import AsyncPostgresStore

            from agent.checkpointing import postgres_checkpointer
            url = os.environ["DATABASE_URL"]
            checkpointer = await stack.enter_async_context(postgres_checkpointer(url))
            store = await stack.enter_async_context(
                AsyncPostgresStore.from_conn_string(url.replace("+psycopg", "")))
            await store.setup()
        else:
            checkpointer, store = MemorySaver(), InMemoryStore()
        if run_mode() == "worker":
            if persistence != "postgres":
                raise RuntimeError("RUN_MODE=worker needs API_PERSISTENCE=postgres")
            from arq import create_pool
            from arq.connections import RedisSettings
            queue = await create_pool(RedisSettings.from_dsn(os.environ["REDIS_URL"]))
            stack.push_async_callback(queue.aclose)
            overrides = {"runs": RedisRunState(queue, worker_settings()["running_ttl_s"]),
                         "queue": queue} | overrides
        runtime = Runtime(checkpointer, store, **overrides)
        try:
            yield runtime
        finally:
            if isinstance(runtime.runs, LocalRunState):
                runtime.runs.cancel_all()
            tracing.flush()  # spans are exported in the background; send what is left


def run_mode() -> str:
    return os.environ.get("RUN_MODE") or load_config()["api"]["run_mode"]


def worker_settings() -> dict[str, Any]:
    return load_config()["worker"]
