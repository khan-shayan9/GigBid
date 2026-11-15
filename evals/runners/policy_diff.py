"""Measure the policy v1 -> v2 change request: compliance on the eval drafts, Connects on dev jobs.

    uv run python -m evals.runners.policy_diff

Drafts are the Phase 4 `final` letters in proposal_eval_dev.json (written under v1). "With
disclosure" appends the line the v2 writer prompt asks for; no model is called again.
"""

import json

from agent.config import load_policy
from agent.nodes.compliance import check
from evals.runners.common import REPO_ROOT, RESULTS, jobs, labels
from gigsim.models import Job
from gigsim.policy import load_policy as load_sim_policy

DISCLOSURE = "This proposal was AI-assisted and reviewed by me."


def draft_rates(rows: list[dict], v1: dict, v2: dict) -> dict:
    letters = [row["final"] for row in rows]
    share = lambda policy, suffix="": round(
        sum(check(letter + suffix, policy).allowed for letter in letters) / len(letters), 3)
    return {"drafts": len(letters), "allowed_v1": share(v1), "allowed_v2": share(v2),
            "allowed_v2_with_disclosure": share(v2, "\n\n" + DISCLOSURE)}


def connects(job_ids: list[str]) -> dict:
    pack = REPO_ROOT / "data" / "policy_pack"
    v1, v2 = load_sim_policy(pack / "v1.yaml"), load_sim_policy(pack / "v2.yaml")
    seed = jobs()
    costs = [(v1.connects_cost(Job(**seed[i])), v2.connects_cost(Job(**seed[i]))) for i in job_ids]
    return {"jobs": len(costs), "mean_v1": round(sum(a for a, _ in costs) / len(costs), 2),
            "mean_v2": round(sum(b for _, b in costs) / len(costs), 2),
            "jobs_costing_more": sum(b > a for a, b in costs)}


def main() -> None:
    v1, v2 = load_policy("v1"), load_policy("v2")
    proposals = json.loads((RESULTS / "proposal_eval_dev.json").read_text(encoding="utf-8"))
    rows = [row for variant in proposals["variants"].values() for row in variant["rows"]]
    dev_ids = sorted({row["job_id"] for row in labels("dev")})
    result = {"note": "v2 is assumed (data/policy_pack/v2.yaml); drafts were written under v1",
              "drafts": draft_rates(rows, v1, v2),
              "connects_dev_jobs": connects(dev_ids),
              "connects_bid_drafts": connects(sorted({row["job_id"] for row in rows}))}
    (RESULTS / "policy_v2_diff.json").write_text(json.dumps(result, indent=2) + "\n",
                                                 encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
