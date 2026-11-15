"""agent/mcp_client.py against real stdio servers: allowlists, refusals, degraded mode, retries."""

import sys
from typing import Any

import pytest

from agent import mcp_client
from agent.config import load_config
from agent.mcp_client import McpClient, ToolFailed, ToolNotAllowed, ToolUnavailable

WINDOW = {"window_start": "2026-11-23T00:00:00+05:00", "window_end": "2026-11-24T00:00:00+05:00"}


def workspace_only(extra: dict[str, Any] | None = None) -> McpClient:
    config = load_config()["mcp"]
    connections = {"workspace": {"transport": "stdio", "command": sys.executable,
                                 "args": ["-m", "mcp_servers.workspace.server"],
                                 "env": {"WORKSPACE_STDIO_USER": "ai_ml_engineer"}}}
    return McpClient("ai_ml_engineer", config, connections | (extra or {}))


async def test_allowlists_and_refusals() -> None:
    async with workspace_only() as mcp:
        slots = await mcp.call("client_liaison", "find_free_slots", WINDOW | {"limit": 2})
        assert len(slots["slots"]) == 2
        with pytest.raises(ToolNotAllowed):
            await mcp.call("writer", "find_free_slots", WINDOW)
        with pytest.raises(ToolFailed, match="invalid_window"):
            await mcp.call("client_liaison", "find_free_slots",
                           {"window_start": WINDOW["window_end"], "window_end": WINDOW["window_start"]})
        tools = {tool.name: tool for tool in await mcp.tools_for("client_liaison")}
        assert set(tools) == {"find_free_slots", "hold_slot", "draft_email"}
        # model-driven calls go through call(): structured result, same refusals
        assert (await tools["find_free_slots"].ainvoke(WINDOW | {"limit": 1}))["slots"]
        assert not await mcp.tools_for("writer")


async def test_a_dead_server_degrades_instead_of_crashing() -> None:
    broken = {"portfolio": {"transport": "stdio", "command": sys.executable,
                            "args": ["-c", "raise SystemExit(1)"]}}
    async with workspace_only(broken) as mcp:
        assert mcp.unavailable == {"portfolio", "marketplace", "github"}
        with pytest.raises(ToolUnavailable):
            await mcp.call("writer", "search_evidence", {"requirement": "rag"})
        assert (await mcp.call("client_liaison", "find_free_slots", WINDOW))["slots"]


async def test_timeouts_retry_reads_but_not_unkeyed_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(mcp_client.asyncio, "sleep", no_sleep)
    async with workspace_only() as mcp:
        session = mcp._sessions["workspace"]
        real_call, calls = session.call_tool, []

        async def flaky(tool: str, args: dict[str, Any]) -> Any:
            calls.append(tool)
            if len(calls) <= 2:
                raise TimeoutError
            return await real_call(tool, args)

        monkeypatch.setattr(session, "call_tool", flaky)
        assert (await mcp.call("client_liaison", "find_free_slots", WINDOW))["slots"]
        assert len(calls) == 3  # two timeouts, then success

        # A write without an idempotency key could act twice, so it gets exactly one try.
        calls.clear()
        monkeypatch.setitem(mcp._tools, "hold_slot", ("workspace", False))
        with pytest.raises(ToolUnavailable):
            await mcp.call("client_liaison", "hold_slot", {"start": "2026-11-23T09:00:00+05:00",
                                                           "title": "Interview"})
        assert calls == ["hold_slot"]


async def test_a_server_that_dies_mid_run_degrades() -> None:
    async with workspace_only() as mcp:
        await mcp._sessions["workspace"]._write_stream.aclose()  # the transport is gone
        with pytest.raises(ToolUnavailable):
            await mcp.call("client_liaison", "find_free_slots", WINDOW)
