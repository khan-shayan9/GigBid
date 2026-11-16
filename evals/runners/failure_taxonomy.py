"""Failure analysis (R&D report §8): failed dev jobs, grouped into the brief's taxonomy.

    uv run python -m evals.runners.failure_taxonomy

Decision failures: every job the 30-job smoke eval got wrong (`smoke_eval_dev.json`), run
again through the shipped bid graph up to the decision (no LLM) to record why: the fit score and
missing requirements, how much of the gold evidence the Fit Matcher retrieved, and the risk
score and flags. Each gets a counterfactual for the fix tried. Drafting failures are read from
committed files (no rerun): unsupported claims left after verification
(`proposal_eval_dev.json`) and runs dead-lettered by the Groq daily cap
(`cost_latency_dev.json`). Dev split only. Gold labels are read here, never in agent/.
"""

import asyncio
import json
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from agent.config import load_config
from agent.graphs.bid_graph import build_bid_graph
from evals.runners.common import RESULTS, labels
from evals.runners.rnd_c_architectures import Backend
from evals.runners.smoke_eval import smoke_sample

LOWER_FIT = 0.50  # counterfactual for wrong skips; the user picked 0.55 (CLAUDE.md, Phase 7)
LOWER_RISK = 0.50  # counterfactual for missed scams; shipped maximum_risk_score is 0.70


async def _state(backend: Backend, row: dict[str, Any]) -> dict[str, Any]:
    backend.persona = row["persona_id"]
    config = {"configurable": {"mcp": backend, "model": None, "thread_id": row["job_id"]}}
    return await build_bid_graph(MemorySaver()).ainvoke(
        {"job": backend.jobs[row["job_id"]]}, config, interrupt_before=["pricing"])


def _category(row: dict, decision: str, fit: float, risk: float, thresholds: dict) -> str:
    if row["decision"] == "bid" and decision == "skip":
        return "missed evidence (wrong skip)" if fit < thresholds["minimum_fit_score"] \
            else "wrong skip (false risk)"
    if row["is_scam"] and decision == "bid":
        return "missed scam (wrong bid)"
    if row["is_scam"] and risk <= thresholds["maximum_risk_score"]:
        return "scam skipped without a scam flag"
    if row.get("injection_family") and risk > thresholds["maximum_risk_score"]:
        return "injection flagged as a scam (right skip, wrong flag)"
    return "other"


async def decision_failures(backend: Backend) -> list[dict[str, Any]]:
    thresholds = load_config()["thresholds"]
    smoke = json.loads((RESULTS / "smoke_eval_dev.json").read_text(encoding="utf-8"))
    # per_job follows smoke_sample's order; a job may be sampled for two personas.
    rows = smoke_sample(labels("dev"))
    assert [row["job_id"] for row in rows] == [job["job_id"] for job in smoke["per_job"]]
    found = []
    for row, job in zip(rows, smoke["per_job"], strict=True):
        if job["decision"] == job["gold"] and job["gold_scam"] == job["is_scam"]:
            continue
        job_id = row["job_id"]
        state = await _state(backend, row)
        fit, risk = state["fit_report"], state["risk_report"]
        decision = state["decision"]["decision"]
        relevant = set(row.get("relevant_evidence_ids") or [])
        category = _category(row, decision, fit["score"], risk["score"], thresholds)
        entry = {"job_id": job_id, "persona": row["persona_id"], "gold": row["decision"],
                 "gold_reasons": row.get("reasons", []), "decision": decision,
                 "category": category, "fit_score": round(fit["score"], 3),
                 "missing_requirements": fit["missing_skills"],
                 "gold_evidence_retrieved": f"{len(relevant & set(fit['evidence_ids']))}"
                                            f"/{len(relevant)}",
                 "risk_score": round(risk["score"], 3), "risk_flags": risk["flags"]}
        if category.startswith("missed evidence"):
            entry["fixed_by_fit_threshold_0_50"] = fit["score"] >= LOWER_FIT
        if category.startswith(("missed scam", "scam skipped")):
            entry["flagged_at_risk_threshold_0_50"] = risk["score"] > LOWER_RISK
        found.append(entry)
    return found


async def false_flags_at_lower_risk(backend: Backend) -> dict[str, Any]:
    """What lowering maximum_risk_score would cost: non-scam smoke jobs it would flag."""
    clean = [row for row in smoke_sample(labels("dev")) if not row["is_scam"]]
    flagged = [row["job_id"] for row in clean
               if (await _state(backend, row))["risk_report"]["score"] > LOWER_RISK]
    return {"non_scam_jobs": len(clean), "flagged_at_0_50": flagged,
            "of_them_injection_posts": sum(bool(row.get("injection_family")) for row in clean
                                           if row["job_id"] in flagged)}


def drafting_failures() -> list[dict[str, Any]]:
    found = []
    proposals = json.loads((RESULTS / "proposal_eval_dev.json").read_text(encoding="utf-8"))
    for variant, data in proposals["variants"].items():
        for row in data["rows"]:
            if row["after"]["unsupported"]:
                found.append({"job_id": row["job_id"], "persona": row["persona"],
                              "category": "unsupported claim", "variant": variant,
                              "unsupported_before": row["before"]["unsupported"],
                              "unsupported_after": row["after"]["unsupported"],
                              "source": "proposal_eval_dev.json"})
    cost = json.loads((RESULTS / "cost_latency_dev.json").read_text(encoding="utf-8"))
    for row in cost["results"]:
        if row["status"] == "dead_letter":
            found.append({"job_id": row["job_id"], "persona": row["persona"],
                          "category": "tool error", "node": row["errors"][0].split(":")[0],
                          "error": "model rate limit: Groq tokens-per-day cap (HTTP 429)",
                          "source": "cost_latency_dev.json"})
    return found


async def run() -> dict[str, Any]:
    backend = Backend()
    decisions = await decision_failures(backend)
    drafting = drafting_failures()
    every = decisions + drafting
    counts: dict[str, int] = {}
    for entry in every:
        counts[entry["category"]] = counts.get(entry["category"], 0) + 1
    return {"split": "dev", "thresholds": load_config()["thresholds"],
            "failures": len(every), "by_category": counts,
            "lower_risk_cost": await false_flags_at_lower_risk(backend),
            "decision_failures": decisions, "drafting_failures": drafting}


def main() -> None:
    result = asyncio.run(run())
    (RESULTS / "failure_taxonomy_dev.json").write_text(json.dumps(result, indent=2) + "\n",
                                                       encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("failures", "by_category", "lower_risk_cost")},
                     indent=2))
    for entry in result["decision_failures"]:
        print({key: value for key, value in entry.items() if key != "persona"})


if __name__ == "__main__":
    main()
