"""Choose `thresholds.minimum_evidence_score`: requirement coverage on dev bid vs skip jobs.

    uv run python -m evals.runners.fit_threshold

For each sampled non-scam, non-injection dev job, every requirement's best evidence score
(search_evidence, the shipped retrieval variant) is compared with each candidate threshold. A
good threshold lets bid jobs reach `thresholds.minimum_fit_score` and stops skip jobs.
"""

import json
import random

from agent.config import load_config
from agent.nodes.writer import requirements
from evals.runners.common import RESULTS, labels
from evals.runners.rnd_c_architectures import Backend

JOBS = 80
SEED = 1
CANDIDATES = (0.55, 0.60, 0.65, 0.70, 0.75)


def main() -> None:
    backend = Backend()
    rows = [row for row in labels("dev") if not row.get("is_scam")
            and not row.get("injection_family")]
    random.Random(SEED).shuffle(rows)
    best: dict[str, list[list[float]]] = {"bid": [], "skip": []}
    for row in rows[:JOBS]:
        backend.persona = row["persona_id"]
        scores = []
        for requirement in requirements(backend.jobs[row["job_id"]]):
            items = backend.run("search_evidence", {"requirement": requirement, "k": 1})["items"]
            scores.append(items[0]["score"] if items else 0.0)
        if scores:
            best[row["decision"]].append(scores)
    minimum_fit = load_config()["thresholds"]["minimum_fit_score"]
    table = {}
    for threshold in CANDIDATES:
        table[str(threshold)] = {}
        for decision, jobs in best.items():
            fits = [sum(score >= threshold for score in job) / len(job) for job in jobs]
            table[str(threshold)][decision] = {
                "jobs": len(fits), "mean_fit": round(sum(fits) / len(fits), 3),
                "share_reaching_minimum_fit": round(
                    sum(fit >= minimum_fit for fit in fits) / len(fits), 3)}
    result = {"split": "dev", "jobs_sampled": JOBS, "seed": SEED,
              "minimum_fit_score": minimum_fit, "thresholds": table}
    (RESULTS / "fit_threshold_dev.json").write_text(json.dumps(result, indent=2) + "\n",
                                                    encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
