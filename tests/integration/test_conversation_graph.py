"""The conversation graph with a fake MCP client and a scripted model (C1, C5)."""

from typing import Any

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from agent.graphs.conversation_graph import build_conversation_graph

SLOT = {"start": "2026-11-17T10:00:00+05:00", "end": "2026-11-17T10:30:00+05:00"}


class FakeMcp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def call(self, node: str, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((node, tool, args))
        return {"slots": [SLOT]} if tool == "find_free_slots" else {"message_id": "m-1"}


async def start(message: str, reply: str) -> tuple[Any, dict, FakeMcp, dict]:
    mcp, graph = FakeMcp(), build_conversation_graph(MemorySaver())
    config = {"configurable": {"mcp": mcp, "model": FakeListChatModel(responses=[reply]),
                               "thread_id": "c1"}}
    result = await graph.ainvoke({"thread_id": "thread-1", "message": message}, config)
    return graph, config, mcp, result


async def test_an_interview_request_gets_slots_and_is_sent_once_after_approval() -> None:
    graph, config, mcp, result = await start("Can we schedule a call this week?",
                                             "Happy to talk. Tuesday 10:00 works for me.")
    payload = result["__interrupt__"][0].value
    assert payload["intent"] == "interview_request" and payload["slots"] == [SLOT]
    assert not [call for call in mcp.calls if call[1] == "send_message"]
    done = await graph.ainvoke(Command(resume={"action": "approve"}), config)
    sends = [args for _, tool, args in mcp.calls if tool == "send_message"]
    assert done["sent"] and len(sends) == 1 and sends[0]["dry_run"] is False


async def test_a_scam_message_is_not_answered() -> None:
    _, _, mcp, result = await start("Let's continue on WhatsApp, send your password.", "ok")
    assert result["intent"] == "scam_signal" and "reply" not in result and not mcp.calls


async def test_a_reply_with_contact_details_is_blocked() -> None:
    _, _, _mcp, result = await start("What is your rate?", "Email me at me@example.com")
    assert result["intent"] == "negotiation" and not result["compliance_verdict"]["allowed"]
    assert "__interrupt__" not in result
