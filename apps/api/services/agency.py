"""Agency mode (X1, ADR 0006): route a new bid thread to the team member who fits the job best.

Runs at the start of the thread's first segment (worker or API task), not in the HTTP request:
each member's Portfolio server is its own MCP connection, and opening them is slow.
"""

import asyncio
import logging
from typing import Any

from agent.config import load_config
from agent.handoffs import FitReport
from agent.mcp_client import ToolUnavailable
from agent.nodes.router import fit_for, route
from apps.api.runtime import Runtime
from apps.api.services import profiles

log = logging.getLogger("gigbid.api")


async def routed_input(rt: Runtime, account: str, persona: str,
                       graph_input: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """(member, graph input) for a thread started with `agency`; the account's persona if no
    member's Portfolio server answers (degraded mode)."""
    job = graph_input["job"]

    async def fit_of(member: str) -> FitReport | None:
        try:
            async with rt.open_mcp(member, ["portfolio"]) as mcp:
                return await fit_for(job, mcp)
        except ToolUnavailable as error:
            log.warning("routing skipped %s: %s", member, error)
            return None

    members = load_config()["api"]["personas"]
    found = await asyncio.gather(*(fit_of(member) for member in members))
    fits = {member: fit for member, fit in zip(members, found, strict=True) if fit is not None}
    if not fits:
        return persona, {"job": job}
    decision = route(fits)
    await profiles.remember_member(rt, account, decision.member)
    return decision.member, {"job": job, "member": decision.member,
                             "route": decision.model_dump()}
