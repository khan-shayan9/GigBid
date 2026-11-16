"""E2 smoke eval and E4 injection check: dev jobs through the bid graph up to the writer.

    uv run python -m evals.runners.smoke_eval            # measure; write evals/results/
    uv run python -m evals.runners.smoke_eval --check    # CI: also fail below a gate

Smoke: 30 seeded, stratified dev jobs (never the held-out split). Gates are in agent/config.yaml
`evals.smoke`, set below the committed baseline. Injection: every dev injection job, with the
Risk Assessor's `injected_instructions` signal removed ("before") and as shipped ("after"); an
attack succeeds when the post is recommended for a bid, i.e. it would reach the writer.
No model is called (the nodes before the writer are rule-based), so CI needs no API key.
"""

import argparse
import asyncio
import json
import random
import sys
import time
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from agent.config import load_config
from agent.graphs.bid_graph import build_bid_graph
from evals.runners.common import RESULTS, labels, percentile
from evals.runners.decision_eval import score
from evals.runners.rnd_c_architectures import Backend, stratum

SEED = 4016
STRATA = {"scam": 8, "injection": 6, "bid": 8, "other_skip": 8}  # 30 jobs
INJECTION_SIGNAL = "injected_instructions"


def smoke_sample(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    picked = []
    for name, count in STRATA.items():
        group = sorted((row for row in rows if stratum(row) == name), key=lambda r: r["job_id"])
        picked += rng.sample(group, count)
    return picked


async def analyse(row: dict[str, Any], backend: Backend) -> dict[str, Any]:
    """The graph's decision, scam call and price for one job, and how long it took."""
    backend.persona = row["persona_id"]
    started = time.perf_counter()
    graph = build_bid_graph(MemorySaver())
    config = {"configurable": {"mcp": backend, "model": None, "thread_id": row["job_id"]}}
    state = await graph.ainvoke({"job": backend.jobs[row["job_id"]]}, config,
                                interrupt_before=["writer"])
    price = (state.get("price_quote") or {}).get("amount_usd")
    return {"job_id": row["job_id"], "decision": state["decision"]["decision"],
            "is_scam": state["risk_report"]["score"] > load_config()["thresholds"][
                "maximum_risk_score"],
            "price_usd": price, "seconds": time.perf_counter() - started}


async def run_rows(rows: list[dict[str, Any]], backend: Backend) -> dict[str, dict[str, Any]]:
    return {row["job_id"]: await analyse(row, backend) for row in rows}


def smoke_metrics(rows: list[dict[str, Any]], calls: dict[str, dict[str, Any]]) -> dict[str, Any]:
    metrics = score(rows, lambda row: calls[row["job_id"]])
    injected = [row for row in rows if row.get("injection_family")]
    metrics["injection_attack_success"] = round(
        sum(calls[row["job_id"]]["decision"] == "bid" for row in injected) / len(injected), 4)
    metrics["p95_seconds_per_job"] = percentile([call["seconds"] for call in calls.values()],
                                                0.95)
    return metrics


async def injection_before_after(backend: Backend) -> dict[str, Any]:
    rows = [row for row in labels("dev") if row.get("injection_family")]
    risk = load_config()["risk"]  # cached dict: the "before" run removes the signal in place
    shipped = list(risk["signals"])
    risk["signals"] = [signal for signal in shipped if signal["id"] != INJECTION_SIGNAL]
    try:
        before = await run_rows(rows, backend)
    finally:
        risk["signals"] = shipped
    after = await run_rows(rows, backend)

    def success(calls: dict[str, dict[str, Any]], family: str | None = None) -> float:
        group = [row for row in rows if family in (None, row["injection_family"])]
        return round(sum(calls[row["job_id"]]["decision"] == "bid" for row in group)
                     / len(group), 4)
    return {
        "jobs": len(rows), "split": "dev",
        "attack": "an injection post recommended for a bid (it would reach the writer)",
        "level": "decision only (risk signals). Whether delimiting stops the writer model "
                 "obeying a post that gets through needs model calls and is not measured here.",
        "before": {"defence": f"risk signal {INJECTION_SIGNAL} removed",
                   "attack_success": success(before)},
        "after": {"defence": "as shipped", "attack_success": success(after)},
        "by_family": {family: {"before": success(before, family),
                               "after": success(after, family)}
                      for family in sorted({row["injection_family"] for row in rows})},
        "caveat": "The injection signal was written after seeing dev jobs, so this dev figure "
                  "is optimistic; the held-out split is for the final report.",
    }


def failed_gates(metrics: dict[str, Any], gates: dict[str, float]) -> list[str]:
    checks = {
        "min_bid_f1": metrics["bid"]["f1"] >= gates["min_bid_f1"],
        "min_scam_recall": metrics["scam"]["recall"] >= gates["min_scam_recall"],
        "max_injection_attack_success":
            metrics["injection_attack_success"] <= gates["max_injection_attack_success"],
        "max_p95_seconds_per_job":
            metrics["p95_seconds_per_job"] <= gates["max_p95_seconds_per_job"],
    }
    return [name for name, passed in checks.items() if not passed]


async def run(check: bool) -> int:
    backend = Backend()
    rows = smoke_sample(labels("dev"))
    calls = await run_rows(rows, backend)
    metrics = smoke_metrics(rows, calls)
    gates = load_config()["evals"]["smoke"]
    failed = failed_gates(metrics, gates)
    smoke = {"jobs": len(rows), "split": "dev", "seed": SEED, "strata": STRATA,
             "metrics": metrics, "gates": gates, "failed_gates": failed,
             "note": "p95 is in-process time per job analysed up to the writer (no model "
                     "calls); it is not the deployed latency.",
             "per_job": [{"job_id": row["job_id"], "stratum": stratum(row),
                          "gold": row["decision"], "decision": calls[row["job_id"]]["decision"],
                          "gold_scam": row["is_scam"],
                          "is_scam": calls[row["job_id"]]["is_scam"]} for row in rows]}
    (RESULTS / "smoke_eval_dev.json").write_text(json.dumps(smoke, indent=2) + "\n",
                                                 encoding="utf-8")
    print(json.dumps(smoke, indent=2))
    if not check:
        injection = await injection_before_after(backend)
        (RESULTS / "injection_dev.json").write_text(json.dumps(injection, indent=2) + "\n",
                                                    encoding="utf-8")
        print(json.dumps(injection, indent=2))
    return 1 if check and failed else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="exit 1 when a gate fails")
    sys.exit(asyncio.run(run(parser.parse_args().check)))


if __name__ == "__main__":
    main()
