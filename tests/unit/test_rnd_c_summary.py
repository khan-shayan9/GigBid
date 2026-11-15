"""R&D C scoring: accuracy, scam-skip rate and unapproved writes from result rows."""

from evals.runners.rnd_c_architectures import summarise


def row(stratum: str, gold: str, said: str, scam: bool = False, writes: int = 0) -> dict:
    return {"stratum": stratum, "gold_decision": gold, "gold_is_scam": stratum == "scam",
            "decision": said, "is_scam": scam, "tool_calls": 2, "write_calls": writes,
            "unapproved_writes": writes, "tokens": 100, "seconds": 1.0, "error": None}


def test_summary_counts_skips_flags_and_unapproved_writes() -> None:
    summary = summarise([row("scam", "skip", "skip", scam=True),
                         row("scam", "skip", "bid", writes=1),
                         row("bid", "bid", "bid"),
                         row("other_skip", "skip", "none")])
    assert summary["decision_accuracy"] == 0.5
    assert summary["scam_skip_rate"] == 0.5 and summary["scam_flag_recall"] == 0.5
    assert summary["bid_precision"] == 0.5 and summary["bid_recall"] == 1.0
    assert summary["no_decision"] == 1 and summary["jobs_with_unapproved_writes"] == 1
