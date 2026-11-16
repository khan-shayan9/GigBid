"""Router (X1 agency mode): send a job to the team member whose portfolio fits it best.

It only picks a member; the decision node still decides bid or skip for that member. It runs
before the bid graph (each member has its own MCP connection; ADR 0006) and uses fit reports
only. Ties on fit score go to the stronger evidence, then to the first member listed.
"""

from typing import Any

from agent.handoffs import FitReport, RouteDecision
from agent.nodes.fit_matcher import fit_matcher


async def fit_for(job: dict[str, Any], mcp: Any) -> FitReport:
    """The shipped Fit Matcher for one member, on that member's Portfolio server."""
    update = await fit_matcher({"job": job}, {"configurable": {"mcp": mcp}})
    return FitReport(**update["fit_report"])


def evidence_strength(fit: FitReport) -> float:
    scores = [match.best_score for match in fit.matrix]
    return sum(scores) / len(scores) if scores else 0.0


def route(fits: dict[str, FitReport]) -> RouteDecision:
    """`fits` in member order; max() keeps the first of equal keys."""
    member = max(fits, key=lambda name: (fits[name].score, evidence_strength(fits[name])))
    best = fits[member]
    tied = [name for name in fits if name != member and fits[name].score == best.score]
    reason = f"fit {best.score:.2f}, the highest"
    if tied:
        reason += f"; tied with {', '.join(tied)}, stronger evidence " \
                  f"({evidence_strength(best):.2f})"
    return RouteDecision(member=member, reason=reason,
                         fit_scores={name: round(fit.score, 3) for name, fit in fits.items()})
