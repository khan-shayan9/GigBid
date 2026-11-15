"""Fit Matcher: map each requirement to portfolio evidence; the fit score is the share covered.

shortcut: a requirement counts as covered when search_evidence returns any item for it; a
model judging each match replaces this when the token budget allows.
"""

from langchain_core.runnables import RunnableConfig

from agent.handoffs import FitReport
from agent.nodes.writer import requirements
from agent.state import GigBidState

NODE = "fit_matcher"
EVIDENCE_PER_REQUIREMENT = 2


async def fit_matcher(state: GigBidState, config: RunnableConfig) -> GigBidState:
    mcp = config["configurable"]["mcp"]
    matched, missing, evidence_ids = [], [], []
    for requirement in requirements(state["job"]):
        result = await mcp.call(NODE, "search_evidence",
                                {"requirement": requirement, "k": EVIDENCE_PER_REQUIREMENT})
        hits = [item["id"] for item in result["items"]]
        (matched if hits else missing).append(requirement)
        evidence_ids += [hit for hit in hits if hit not in evidence_ids]
    total = len(matched) + len(missing)
    report = FitReport(score=len(matched) / total if total else 0.0, matched_skills=matched,
                       missing_skills=missing, evidence_ids=evidence_ids)
    return {"fit_report": report.model_dump()}
