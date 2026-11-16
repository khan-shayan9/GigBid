"""X1 agency mode: the router picks the best-fit member and only that (ADR 0006)."""

from agent.handoffs import FitReport, RequirementMatch
from agent.nodes.router import route


def fit(score: float, *best: float) -> FitReport:
    return FitReport(score=score, matrix=[RequirementMatch(requirement=f"r{i}", best_score=value)
                                          for i, value in enumerate(best)])


def test_the_highest_fit_wins() -> None:
    decision = route({"a": fit(0.5, 0.7, 0.6), "b": fit(1.0, 0.7, 0.7), "c": fit(0.0)})
    assert decision.member == "b" and decision.fit_scores == {"a": 0.5, "b": 1.0, "c": 0.0}
    assert "tied" not in decision.reason


def test_a_tie_goes_to_stronger_evidence_then_to_the_first_member() -> None:
    assert route({"a": fit(1.0, 0.70), "b": fit(1.0, 0.80)}).member == "b"
    assert route({"a": fit(0.0), "b": fit(0.0)}).member == "a"
