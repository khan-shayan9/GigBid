"""B4 decisions: bid-or-skip F1, scam precision and recall, price inside the fair band.

The decision, risk and pricing nodes arrive in Phase 5; until then this runner holds the scoring
and is tested with a stand-in `decide`. Phase 5 passes the bid graph as `decide`.
"""

from collections.abc import Callable
from typing import Any, TypedDict


class Decision(TypedDict):
    decision: str  # "bid" or "skip" ("watch" counts as skip)
    is_scam: bool
    price_usd: float | None


Decide = Callable[[dict[str, Any]], Decision]  # one gold label row in, the system's call out


def _f1(true_positive: int, false_positive: int, false_negative: int) -> dict[str, float]:
    precision = true_positive / (true_positive + false_positive) if true_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def score(rows: list[dict[str, Any]], decide: Decide) -> dict[str, Any]:
    calls = [(row, decide(row)) for row in rows]
    bid = [(row["decision"] == "bid", call["decision"] == "bid") for row, call in calls]
    scam = [(row["is_scam"], call["is_scam"]) for row, call in calls]
    priced = [(row, call) for row, call in calls
              if row["decision"] == "bid" and call["decision"] == "bid" and call["price_usd"]]
    in_band = sum(row["fair_price_band"]["min_usd"] <= call["price_usd"]
                  <= row["fair_price_band"]["max_usd"] for row, call in priced)
    return {
        "jobs": len(rows),
        "bid": _f1(*_counts(bid)),
        "scam": _f1(*_counts(scam)),
        "price_in_band": round(in_band / len(priced), 4) if priced else None,
        "priced_jobs": len(priced),
    }


def _counts(pairs: list[tuple[bool, bool]]) -> tuple[int, int, int]:
    return (sum(gold and said for gold, said in pairs),
            sum(said and not gold for gold, said in pairs),
            sum(gold and not said for gold, said in pairs))
