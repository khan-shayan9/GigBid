"""What the API's services share for the app's lifetime: persistence, graphs, MCP and models.

The checkpointer and store are Postgres when API_PERSISTENCE=postgres (docker compose, deploy),
else in memory (local dev and tests). `open_mcp` and `model_for` are injectable, so end-to-end
tests run the real API against a fake marketplace and a scripted model (tests/e2e/).
"""

import asyncio
import os
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from agent.config import load_config
from agent.graphs.bid_graph import build_bid_graph
from agent.graphs.conversation_graph import build_conversation_graph
from agent.llm import chat_model
from agent.mcp_client import McpClient

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
    bid_graph: Any = None
    conversation_graph: Any = None
    # Threads with a graph segment running now, and their live SSE listeners.
    running: dict[str, asyncio.Task] = field(default_factory=dict)
    listeners: dict[str, list[asyncio.Queue]] = field(default_factory=dict)
    # Why a run stopped on an error, for runs that failed before their first checkpoint.
    failures: dict[str, str] = field(default_factory=dict)

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
        runtime = Runtime(checkpointer, store, **overrides)
        try:
            yield runtime
        finally:
            for task in list(runtime.running.values()):
                task.cancel()
