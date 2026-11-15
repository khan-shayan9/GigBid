"""Part B scoring: retrieval metrics, judge kappa, decision metrics and judge-reply parsing."""

import pytest

from evals.runners.ablation import ablations
from evals.runners.decision_eval import score
from evals.runners.judge_calibration import cohen_kappa
from evals.runners.proposal_eval import judge_score
from evals.runners.rag_eval import ndcg_at, recall_at, reciprocal_rank


def test_retrieval_metrics() -> None:
    ranked, gold = ["x", "a", "y", "b"], {"a", "b", "c"}
    assert recall_at(ranked, gold, 2) == pytest.approx(1 / 3)
    assert reciprocal_rank(ranked, gold) == 0.5 and reciprocal_rank(["x"], gold) == 0.0
    assert ndcg_at(["a", "b", "c"], gold, 10) == pytest.approx(1.0)
    assert 0 < ndcg_at(ranked, gold, 10) < 1


def test_kappa() -> None:
    assert cohen_kappa([1, 2, 3, 4], [1, 2, 3, 4]) == 1.0
    assert cohen_kappa([1, 2, 1, 2], [2, 1, 2, 1]) < 0
    near = cohen_kappa([1, 2, 3, 4, 5], [2, 3, 4, 5, 5], weighted=True)
    assert near > cohen_kappa([1, 2, 3, 4, 5], [2, 3, 4, 5, 5])


def test_decision_metrics() -> None:
    band = {"min_usd": 10, "max_usd": 20}
    rows = [{"decision": "bid", "is_scam": False, "fair_price_band": band},
            {"decision": "skip", "is_scam": True, "fair_price_band": band},
            {"decision": "bid", "is_scam": False, "fair_price_band": band}]
    calls = iter([{"decision": "bid", "is_scam": False, "price_usd": 15.0},
                  {"decision": "skip", "is_scam": True, "price_usd": None},
                  {"decision": "skip", "is_scam": False, "price_usd": None}])
    result = score(rows, lambda _: next(calls))
    assert result["bid"] == {"precision": 1.0, "recall": 0.5, "f1": 0.6667}
    assert result["scam"]["recall"] == 1.0 and result["price_in_band"] == 1.0


def test_judge_reply_parsing_takes_the_last_json() -> None:
    assert judge_score('<think>maybe {"score": 2}</think> {"score": 4, "reason": "ok"}') == 4
    assert judge_score("no json") is None and judge_score('{"score": 9}') is None


def test_ablation_drops_one_switch_at_a_time() -> None:
    names = ablations("best", {"decompose": True, "hybrid": True, "rerank": False})
    assert set(names) == {"best", "best-without-decompose", "best-without-hybrid"}
