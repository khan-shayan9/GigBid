"""Portfolio MCP resource templates: one case study, one past proposal."""

import json

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ResourceError

from mcp_servers.portfolio.store import PortfolioStore


def register_resources(mcp: FastMCP, store: PortfolioStore) -> None:
    @mcp.resource("portfolio://case/{case_id}", mime_type="text/markdown")
    async def case_study(case_id: str) -> str:
        """One case study as Markdown."""
        item = await store.find(case_id, "case_study")
        if not item:
            raise ResourceError(f"case_study_not_found: {case_id}")
        return f"# {item.title}\n\n{item.text}\n"

    @mcp.resource("portfolio://proposal/{proposal_id}", mime_type="application/json")
    async def past_proposal(proposal_id: str) -> str:
        """One past proposal with its date and outcome (won, replied or ignored)."""
        item = await store.find(proposal_id, "proposal")
        if not item:
            raise ResourceError(f"proposal_not_found: {proposal_id}")
        return json.dumps(item.model_dump())
