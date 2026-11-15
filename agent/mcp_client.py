"""The agents' only door to MCP servers: per-node tool allowlists, timeouts, retries, degraded mode.

Use as `async with McpClient(user) as mcp:`. It keeps one session per server for the run. A server
that cannot be reached is marked unavailable and the others keep working (degraded mode).
"""

import asyncio
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Self

import anyio
from langchain_core.tools import BaseTool, StructuredTool
from langchain_mcp_adapters.sessions import Connection, create_session
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp import ClientSession
from mcp.shared.exceptions import McpError

from agent.config import load_config
from mcp_servers.auth import parse_tokens

BACKOFF_BASE_S = 0.5
REPO_ROOT = Path(__file__).resolve().parents[1]
# A dead or hung server surfaces as one of these, never as a tool refusal.
TRANSPORT_ERRORS = (TimeoutError, OSError, McpError, anyio.ClosedResourceError,
                    anyio.BrokenResourceError)
# Refusals that mean "the dependency is down", not "the request is wrong".
UNAVAILABLE_CODES = ("marketplace_unavailable", "rate_limited")


class ToolNotAllowed(Exception):
    """The node asked for a tool outside its allowlist."""


class ToolUnavailable(Exception):
    """The server is down or timed out after retries: degrade, queue the work, try later."""


class ToolFailed(Exception):
    """The tool refused the call (bad input, not found, policy). Retrying will not help."""


def connections_for(user: str, config: dict) -> dict[str, Connection]:
    """How to reach each server as `user`: a local stdio process, or HTTP with their token."""
    connections: dict[str, Connection] = {}
    for name, server in config["servers"].items():
        if "token_env" in server:  # a third-party server: HTTP with one shared read-only token
            if os.environ.get(server["token_env"]):
                connections[name] = {"transport": "streamable_http", "url": server["url"],
                                     "headers": server.get("headers", {}) | {
                                         "Authorization": f"Bearer {os.environ[server['token_env']]}"}}
            continue
        prefix = server["env_prefix"]
        if config["transport"] == "stdio":
            connections[name] = {"transport": "stdio", "command": sys.executable,
                                 "args": ["-m", server["module"]], "cwd": str(REPO_ROOT),
                                 "env": {f"{prefix}_STDIO_USER": user}}
            continue
        tokens = parse_tokens(os.environ.get(f"{prefix}_MCP_TOKENS", ""), f"{prefix}_MCP_TOKENS")
        token = next((token for token, owner in tokens.items() if owner == user), None)
        if token:  # no token for this user: leave the server out, so it counts as unavailable
            connections[name] = {"transport": "streamable_http", "url": server["url"],
                                 "headers": {"Authorization": f"Bearer {token}"}}
    return connections


class McpClient:
    def __init__(self, user: str, config: dict | None = None,
                 connections: dict[str, Connection] | None = None,
                 servers: list[str] | None = None) -> None:
        """`servers` limits the run to those servers (default: all in config)."""
        self.config = config or load_config()["mcp"]
        if servers is not None:
            self.config = self.config | {"servers": {
                name: self.config["servers"][name] for name in servers}}
        self.connections = connections if connections is not None else connections_for(
            user, self.config)
        self.unavailable: set[str] = set(self.config["servers"]) - set(self.connections)
        self._sessions: dict[str, ClientSession] = {}
        self._tools: dict[str, tuple[str, bool]] = {}  # tool -> (server, read-only)
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> Self:
        for name, connection in self.connections.items():
            try:
                # asyncio.timeout, not wait_for: the session's task group must stay in this task.
                async with asyncio.timeout(self.config["timeout_s"]):
                    session = await self._stack.enter_async_context(create_session(connection))
                    await session.initialize()
                    listed = (await session.list_tools()).tools
                for tool in listed:  # first server wins: a third party cannot shadow our tools
                    read_only = bool(tool.annotations and tool.annotations.readOnlyHint)
                    self._tools.setdefault(tool.name, (name, read_only))
                self._sessions[name] = session
            except Exception:  # noqa: BLE001 - any start-up failure means degraded, not a crash
                self.unavailable.add(name)
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._stack.aclose()

    def allowed(self, node: str) -> list[str]:
        return list(self.config["allowlists"].get(node, []))

    async def tools_for(self, node: str) -> list[BaseTool]:
        """LangChain tools for a tool-calling model: only this node's allowlist, live servers.

        Each tool runs through `call`, so model-driven calls get the same timeouts, retries and
        degraded mode.
        """
        tools: list[BaseTool] = []
        for name, session in self._sessions.items():
            for tool in await load_mcp_tools(session, server_name=name):
                if tool.name in self.allowed(node) and self._tools[tool.name][0] == name:
                    tools.append(self._guarded(node, tool))
        return tools

    def _guarded(self, node: str, tool: BaseTool) -> BaseTool:
        async def run(**args: Any) -> dict[str, Any]:
            return await self.call(node, tool.name, args)

        return StructuredTool.from_function(coroutine=run, name=tool.name,
                                            description=tool.description,
                                            args_schema=tool.args_schema)

    async def call(self, node: str, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        """Call one tool for one node; returns the tool's structured result."""
        if tool not in self.allowed(node):
            raise ToolNotAllowed(f"{node} may not call {tool}")
        if tool not in self._tools:
            raise ToolUnavailable(f"{tool}: its server is unavailable")
        server, read_only = self._tools[tool]
        # Retrying is safe only when the call cannot act twice.
        attempts = 1 + (self.config["retries"] if read_only or "idempotency_key" in args else 0)
        for attempt in range(attempts):
            try:
                async with asyncio.timeout(self.config["timeout_s"]):
                    result = await self._sessions[server].call_tool(tool, args)
            except TRANSPORT_ERRORS as error:
                if attempt == attempts - 1:
                    raise ToolUnavailable(f"{tool}: {type(error).__name__}") from error
                await asyncio.sleep(BACKOFF_BASE_S * 2 ** attempt)
                continue
            if not result.isError:
                return result.structuredContent or {"content": _texts(result.content)}
            message = result.content[0].text.removeprefix(f"Error executing tool {tool}: ") \
                if result.content else "unknown error"
            if message.startswith(UNAVAILABLE_CODES):
                raise ToolUnavailable(message)
            raise ToolFailed(message)
        raise AssertionError("unreachable")


def _texts(content: list[Any]) -> list[str]:
    """Plain text from a result without structured content (e.g. GitHub file contents)."""
    resources = [getattr(part, "resource", None) for part in content]
    return [text for text in [getattr(part, "text", None) for part in content]
            + [getattr(resource, "text", None) for resource in resources] if text]
