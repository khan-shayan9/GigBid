"""Decision node: the only place that decides bid or skip (2.ARCHITECTURE.md §10)."""

from agent.config import load_config
from agent.handoffs import BidDecision, FitReport, RiskReport
from agent.state import GigBidState


def decide(risk: RiskReport, fit: FitReport, thresholds: dict) -> BidDecision:
    reasons = []
    if risk.score > thresholds["maximum_risk_score"]:
        reasons.append(f"risk {risk.score:.2f} above {thresholds['maximum_risk_score']}: "
                       f"{risk.explanation}")
    if fit.score < thresholds["minimum_fit_score"]:
        reasons.append(f"fit {fit.score:.2f} below {thresholds['minimum_fit_score']}")
    return BidDecision(decision="skip" if reasons else "bid", reasons=reasons)


async def decision(state: GigBidState) -> GigBidState:
    verdict = decide(RiskReport(**state["risk_report"]), FitReport(**state["fit_report"]),
                     load_config()["thresholds"])
    return {"decision": verdict.model_dump()}
