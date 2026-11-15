"""Judge calibration (B4) and the blind human panel: export sheets, then score agreement.

The 30 hand labels and the panel ratings are the user's own work (spec §10); this only
prepares the sheets and computes the numbers from them.

  export  -> evals/datasets/judge_calibration_items.jsonl and judge_calibration_labels.csv
             (up to 30 letters with their evidence; blind: no judge score or variant),
             judge_calibration_key.jsonl (judge scores; do not open before labelling), and
             evals/datasets/panel_pairs.csv (anonymised pairs of letters for the same job)
  score   -> evals/results/judge_calibration.json: Cohen's kappa (plain and quadratic-weighted)
             between the filled-in human_score column and the judge's scores
Run: `uv run python -m evals.runners.judge_calibration export|score`
"""

import csv
import hashlib
import json
import random
import sys
from collections import Counter
from typing import Any

from evals.runners.common import DATASETS, PERSONAS, RESULTS, job_post, jobs
from rag.ingest.portfolio import load_portfolio

ITEMS = DATASETS / "judge_calibration_items.jsonl"
LABELS = DATASETS / "judge_calibration_labels.csv"
KEY = DATASETS / "judge_calibration_key.jsonl"
PANEL = DATASETS / "panel_pairs.csv"
CALIBRATION_ITEMS = 30
SCALE = range(1, 6)


def cohen_kappa(first: list[int], second: list[int], weighted: bool = False) -> float:
    """Cohen's kappa on the 1-5 scale; quadratic weights when `weighted`."""
    total = len(first)

    def weight(a: int, b: int) -> float:
        return ((a - b) / (max(SCALE) - min(SCALE))) ** 2 if weighted else float(a != b)

    seen = Counter(zip(first, second, strict=True))
    first_counts, second_counts = Counter(first), Counter(second)
    observed = sum(weight(a, b) * count for (a, b), count in seen.items()) / total
    expected = sum(weight(a, b) * first_counts[a] * second_counts[b]
                   for a in SCALE for b in SCALE) / total ** 2
    return round(1 - observed / expected, 4) if expected else 1.0


def _proposals() -> list[dict[str, Any]]:
    data = json.loads((RESULTS / "proposal_eval_dev.json").read_text(encoding="utf-8"))
    return [row for variant in data["variants"].values() for row in variant["rows"]
            if row["final"] and row["judge_score"] is not None]


def export() -> None:
    rows = sorted(_proposals(), key=lambda row: hashlib.sha256(
        f"{row['variant']}|{row['job_id']}".encode()).hexdigest())[:CALIBRATION_ITEMS]
    all_jobs = jobs()
    evidence = {persona: {item.id: f"[{item.id}] {item.title}: {item.text[:600]}"
                          for item in load_portfolio(PERSONAS / persona)}
                for persona in {row["persona"] for row in rows}}
    with ITEMS.open("w", encoding="utf-8") as items, KEY.open("w", encoding="utf-8") as key:
        for number, row in enumerate(rows, start=1):
            item_id = f"cal-{number:02d}"
            items.write(json.dumps({
                "item_id": item_id, "job_id": row["job_id"], "persona": row["persona"],
                "job_post": job_post(all_jobs[row["job_id"]]), "letter": row["final"],
                "evidence": [evidence[row["persona"]][id_] for id_ in row["evidence_ids"]]})
                + "\n")
            key.write(json.dumps({"item_id": item_id, "variant": row["variant"],
                                  "judge_score": row["judge_score"]}) + "\n")
    with LABELS.open("w", newline="", encoding="utf-8") as labels:
        writer = csv.writer(labels)
        writer.writerow(["item_id", "human_score"])
        writer.writerows([[f"cal-{number:02d}", ""] for number in range(1, len(rows) + 1)])
    by_job: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in _proposals():
        by_job.setdefault((row["persona"], row["job_id"]), []).append(row)
    rng = random.Random(4016)
    with PANEL.open("w", newline="", encoding="utf-8") as panel:
        writer = csv.writer(panel)
        writer.writerow(["pair_id", "job_id", "letter_a", "letter_b", "preferred (a/b/tie)"])
        for number, (key, pair) in enumerate(sorted(by_job.items()), start=1):
            if len(pair) == 2 and pair[0]["final"] != pair[1]["final"]:
                rng.shuffle(pair)
                writer.writerow([f"pair-{number:02d}", key[1], pair[0]["final"],
                                 pair[1]["final"], ""])
    print(f"wrote {ITEMS.name}, {LABELS.name} (fill human_score 1-5) and {PANEL.name}")


def score() -> None:
    judge = {row["item_id"]: row["judge_score"] for row in
             (json.loads(line) for line in KEY.read_text(encoding="utf-8").splitlines())}
    with LABELS.open(encoding="utf-8") as labels:
        human = {row["item_id"]: int(row["human_score"]) for row in csv.DictReader(labels)
                 if row["human_score"].strip()}
    ids = sorted(human)
    if not ids:
        raise SystemExit(f"no human scores yet in {LABELS}")
    first, second = [human[item] for item in ids], [judge[item] for item in ids]
    result = {"items": len(ids), "cohen_kappa": cohen_kappa(first, second),
              "quadratic_weighted_kappa": cohen_kappa(first, second, weighted=True),
              "exact_agreement": round(sum(a == b for a, b in zip(first, second,
                                                                   strict=True)) / len(ids), 4)}
    (RESULTS / "judge_calibration.json").write_text(json.dumps(result, indent=1) + "\n",
                                                    encoding="utf-8")
    print(result)


if __name__ == "__main__":
    {"export": export, "score": score}[sys.argv[1]]()
