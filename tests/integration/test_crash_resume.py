"""Crash, resume and replay of the bid graph: the proposal is submitted exactly once (C6).

The crash happens after the marketplace accepted the submission but before the step was
checkpointed, the worst case: the resumed run calls submit_proposal again with the same
idempotency key, and the marketplace (like GigSim) returns the first result.
A new graph object on the same checkpointer stands in for a restarted process. With
DATABASE_URL set (CI), the same test also runs on the Postgres checkpointer.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from agent.graphs.bid_graph import build_bid_graph
from tests.integration.test_bid_graph import GOOD, JOB
from tests.integration.test_bid_graph import FakeMcp as BaseMcp


class Crash(RuntimeError):
    """The worker process dies."""


class IdempotentMcp(BaseMcp):
    """Honours idempotency keys like GigSim, and crashes once right after the first submit."""

    def __init__(self) -> None:
        super().__init__()
        self.results: dict[str, dict[str, Any]] = {}
        self.submissions = 0
        self.submit_attempts = 0
        self.crash_after_submit = True

    async def call(self, node: str, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        key = args.get("idempotency_key")
        self.submit_attempts += tool == "submit_proposal"
        if key in self.results:
            return self.results[key]
        result = await super().call(node, tool, args)
        if key:
            self.results[key] = result
        if tool == "submit_proposal":
            self.submissions += 1
            if self.crash_after_submit:
                self.crash_after_submit = False
                raise Crash
        return result


@asynccontextmanager
async def memory_saver() -> AsyncIterator[MemorySaver]:
    yield MemorySaver()


@asynccontextmanager
async def postgres_saver() -> AsyncIterator[Any]:
    from agent.checkpointing import postgres_checkpointer
    async with postgres_checkpointer(os.environ["DATABASE_URL"]) as saver:
        yield saver


SAVERS = [memory_saver, pytest.param(postgres_saver, marks=pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="needs Postgres (DATABASE_URL)"))]


@pytest.mark.parametrize("open_saver", SAVERS)
async def test_a_crash_after_submit_resumes_and_submits_exactly_once(open_saver: Any) -> None:
    mcp = IdempotentMcp()
    config = {"configurable": {"mcp": mcp, "model": FakeListChatModel(responses=[GOOD, "[]"]),
                               "thread_id": f"crash-{os.getpid()}-{id(mcp)}"}}
    async with open_saver() as saver:
        first = build_bid_graph(saver)
        paused = await first.ainvoke({"job": JOB}, config)
        assert "__interrupt__" in paused and mcp.submissions == 0
        with pytest.raises(Crash):
            await first.ainvoke(Command(resume={"action": "approve"}), config)

        restarted = build_bid_graph(saver)  # a new process on the same checkpoints
        assert (await restarted.aget_state(config)).next == ("submit",)
        done = await restarted.ainvoke(None, config)
        assert done["approval_status"] == "approved"
        assert done["submission"]["proposal"]["status"] == "submitted"
        assert mcp.submissions == 1  # the resumed call hit the idempotency key

        # Replay from the checkpoint before submit re-runs it; still one submission.
        history = [state async for state in restarted.aget_state_history(config)]
        before_submit = next(state for state in history if state.next == ("submit",))
        await restarted.ainvoke(None, {"configurable": {
            **config["configurable"], **before_submit.config["configurable"]}})
        assert mcp.submissions == 1 and mcp.submit_attempts == 3  # first, resume, replay
