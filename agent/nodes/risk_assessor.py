"""Risk Assessor: flag scams, off-platform asks and injected instructions; score the client.

Signals are patterns in config (`risk.signals`), each with a weight; the client's history comes
from the Marketplace MCP tool `get_client_history`. The post is only read, never obeyed.
"""

import re
from typing import Any

from langchain_core.runnables import RunnableConfig

from agent.config import load_config
from agent.handoffs import RiskReport
from agent.mcp_client import ToolUnavailable
from agent.state import GigBidState

NODE = "risk_assessor"


def assess(job: dict[str, Any], client: dict[str, Any] | None, settings: dict) -> RiskReport:
    text = f"{job['title']}\n{job['description']}"
    flags = [signal["id"] for signal in settings["signals"]
             if re.search(signal["pattern"], text, re.IGNORECASE)]
    score = sum(signal["weight"] for signal in settings["signals"] if signal["id"] in flags)
    if client is not None and not client.get("payment_verified") \
            and not client.get("total_spent_usd"):
        flags.append("unverified_new_client")
        score += settings["unverified_client_weight"]
    if client is None:
        flags.append("client_history_unavailable")
    return RiskReport(score=min(score, 1.0), flags=flags,
                      explanation=", ".join(flags) or "no risk signals found")


async def risk_assessor(state: GigBidState, config: RunnableConfig) -> GigBidState:
    job = state["job"]
    try:
        client = await config["configurable"]["mcp"].call(
            NODE, "get_client_history", {"client_id": job["client_id"]})
    except ToolUnavailable:  # degraded mode: judge the post alone and say so
        client = None
    return {"risk_report": assess(job, client, load_config()["risk"]).model_dump()}
