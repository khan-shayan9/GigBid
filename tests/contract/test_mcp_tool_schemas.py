"""Fail CI when an MCP tool, resource template or prompt signature changes unintentionally.

After an intended change, regenerate with `UPDATE_SNAPSHOTS=1 uv run pytest tests/contract` and
commit the snapshot diff with the change.
"""

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session

from mcp_servers.marketplace.server import ServerSettings, create_server
from mcp_servers.portfolio import server as portfolio
from mcp_servers.portfolio.store import PortfolioSettings
from mcp_servers.workspace import server as workspace
from rag.index.embedder import FakeEmbedder

SNAPSHOTS = Path(__file__).parent / "snapshots"


async def tool_signatures(server: FastMCP) -> dict:
    async with create_connected_server_and_client_session(server) as session:
        tools = (await session.list_tools()).tools
        templates = (await session.list_resource_templates()).resourceTemplates
        prompts = (await session.list_prompts()).prompts
    signatures = {tool.name: tool.model_dump(mode="json", exclude_none=True,
                                             include={"description", "inputSchema",
                                                      "outputSchema", "annotations"})
                  for tool in tools}
    signatures |= {f"resource:{template.uriTemplate}": template.model_dump(
        mode="json", exclude_none=True, include={"description", "mimeType"})
        for template in templates}
    signatures |= {f"prompt:{prompt.name}": prompt.model_dump(
        mode="json", exclude_none=True, include={"description", "arguments"})
        for prompt in prompts}
    return dict(sorted(signatures.items()))


async def check_snapshot(name: str, server: FastMCP) -> None:
    path = SNAPSHOTS / f"{name}.json"
    current = await tool_signatures(server)
    if os.environ.get("UPDATE_SNAPSHOTS"):
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert current == json.loads(path.read_text(encoding="utf-8")), (
        f"{name} MCP tool signatures changed; see this file's docstring to accept the change")


async def test_marketplace_tool_schemas(tmp_path: Path) -> None:
    server = create_server(ServerSettings(audit_path=tmp_path / "audit.jsonl"),
                           port_for=lambda user: None)
    await check_snapshot("marketplace", server)


async def test_portfolio_tool_schemas() -> None:
    await check_snapshot("portfolio", portfolio.create_server(
        PortfolioSettings(cache_dir=None), FakeEmbedder()))


async def test_workspace_tool_schemas(tmp_path: Path) -> None:
    await check_snapshot("workspace", workspace.create_server(
        workspace.WorkspaceSettings(store_dir=tmp_path)))
