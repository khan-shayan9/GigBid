"""B5: build the results table (report and README) from the files in evals/results/.

Run: `uv run python -m evals.runners.results_table` -> evals/results/rag_results_table.md
Cells with no measurement say "n/m" (not measured) instead of a number.
"""

import json
from typing import Any

from evals.runners.common import RESULTS

OUT = RESULTS / "rag_results_table.md"


def _load(name: str) -> dict[str, Any]:
    path = RESULTS / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _cell(value: Any) -> str:
    return "n/m" if value is None else str(value)


def table() -> str:
    retrieval = _load("rag_retrieval_dev.json").get("variants", {})
    proposals = _load("proposal_eval_dev.json").get("variants", {})
    kappa = _load("judge_calibration.json")
    lines = [
        ("| Variant | Evidence Recall@5 | nDCG@10 | MRR | Unsupported claims per proposal "
        "(before -> after verification) | Judge score (1-5) | GigSim reply rate | "
        "p95 latency (s) | Cost per proposal (USD) |"),
        "|---|---|---|---|---|---|---|---|---|"]
    for name in dict.fromkeys([*retrieval, *proposals]):
        metrics = retrieval.get(name, {}).get("overall", {})
        quality = proposals.get(name, {}).get("overall")
        unsupported = (f"{quality['unsupported_per_proposal']['before']} -> "
                       f"{quality['unsupported_per_proposal']['after']}") if quality else None
        lines.append("| " + " | ".join([
            name, _cell(metrics.get("recall_at_5")), _cell(metrics.get("ndcg_at_10")),
            _cell(metrics.get("mrr")), _cell(unsupported),
            _cell(quality and quality["judge_score"]),
            _cell(quality and quality["gigsim"]["reply_rate"]),
            _cell(quality and quality["latency_s"]["p95"]),
            _cell(quality and quality["usd_per_proposal"])]) + " |")
    calibration = (f"Cohen's kappa {kappa['cohen_kappa']} (quadratic-weighted "
                   f"{kappa['quadratic_weighted_kappa']}) on {kappa['items']} hand-labelled items"
                   if kappa else "the judge is **not yet calibrated** (no hand labels yet)")
    sources = ("Sources: `evals/results/rag_retrieval_dev.json`, "
               "`evals/results/proposal_eval_dev.json`, `evals/results/judge_calibration.json`.")
    return "\n".join([*lines, "", f"Judge: {calibration}.", sources, ""])


def main() -> None:
    OUT.write_text(table(), encoding="utf-8")
    print(OUT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
