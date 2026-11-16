"""R8 / E5: measured latency and tokens per job analysed and per proposal, on real models.

    uv run python -m evals.runners.cost_latency --jobs 8

Seeded dev jobs labelled "bid" run through the whole bid graph up to the approval pause, with
the deployed model routing (`api.run_models.bid` on the active profile, Groq by default). The
tools are the in-process seed backend (evals/runners/rnd_c_architectures.Backend), so the
times leave out MCP process start-up and GigSim network calls; they include model latency and
Groq rate-limit waits. Tokens per node come from the graph's own guard (agent/graphs/guard.py).
USD is not computed: model prices are not set yet. Writes evals/results/cost_latency_dev.json.
"""

import argparse
import asyncio
import json
import random
import re
import time
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from agent.config import load_config
from agent.graphs.bid_graph import build_bid_graph
from agent.llm import chat_model
from evals.runners.common import MAX_RETRIES, RESULTS, labels, percentile
from evals.runners.rnd_c_architectures import Backend, stratum

SEED = 4016


def masked(error: str) -> str:
    """Provider errors name the account's organisation id; keep it out of committed results."""
    return re.sub(r"org_\w+", "org_[masked]", error)


async def run_job(row: dict[str, Any], backend: Backend, model: Any) -> dict[str, Any]:
    backend.persona = row["persona_id"]
    graph = build_bid_graph(MemorySaver())
    config = {"configurable": {"mcp": backend, "model": model, "thread_id": row["job_id"],
                               "user_id": "eval"}}
    started = time.perf_counter()
    marks: dict[str, float] = {}
    tokens: dict[str, int] = {}
    async for chunk in graph.astream({"job": backend.jobs[row["job_id"]]}, config,
                                     stream_mode="updates"):
        for node, update in chunk.items():
            marks[node] = round(time.perf_counter() - started, 3)
            if isinstance(update, dict) and update.get("tokens_used"):
                tokens[node] = tokens.get(node, 0) + update["tokens_used"]
    state = (await graph.aget_state(config)).values
    drafted = bool(state.get("proposal_draft")) and "__interrupt__" in marks
    return {"job_id": row["job_id"], "persona": row["persona_id"],
            "decision": (state.get("decision") or {}).get("decision"),
            "status": state.get("status"), "errors": [masked(e) for e in state.get("errors", [])],
            "seconds_to_decision": marks.get("decision"),
            "seconds_to_approval": marks.get("__interrupt__") if drafted else None,
            "drafted": drafted, "revisions": state.get("revisions", 0),
            "tokens_by_node": tokens, "tokens": sum(tokens.values())}


def summarise(results: list[dict[str, Any]]) -> dict[str, Any]:
    decided = [r["seconds_to_decision"] for r in results if r["seconds_to_decision"] is not None]
    drafted = [r for r in results if r["drafted"]]
    by_node: dict[str, list[int]] = {}
    for result in drafted:
        for node, count in result["tokens_by_node"].items():
            by_node.setdefault(node, []).append(count)
    return {
        "per_job_analysed": {"jobs": len(decided), "p50_seconds": percentile(decided, 0.5),
                             "p95_seconds": percentile(decided, 0.95)},
        "per_proposal": {
            "proposals": len(drafted),
            "p50_seconds": percentile([r["seconds_to_approval"] for r in drafted], 0.5),
            "p95_seconds": percentile([r["seconds_to_approval"] for r in drafted], 0.95),
            "p50_tokens": percentile([r["tokens"] for r in drafted], 0.5),
            "p95_tokens": percentile([r["tokens"] for r in drafted], 0.95),
            "mean_tokens_by_node": {node: round(sum(v) / len(v)) for node, v in
                                    sorted(by_node.items())},
        },
        "token_budget_per_job": load_config()["budgets"]["max_tokens_per_job"],
        "over_budget": sum(r["status"] == "needs_attention" for r in results),
        "dead_lettered": sum(r["status"] == "dead_letter" for r in results),
        "usd": None,
    }


async def run(jobs: int) -> dict[str, Any]:
    rows = sorted((row for row in labels("dev") if stratum(row) == "bid"),
                  key=lambda row: row["job_id"])
    rows = random.Random(SEED).sample(rows, jobs)
    node = load_config()["api"]["run_models"]["bid"]
    model = chat_model(node, max_retries=MAX_RETRIES)  # rate limits wait, not fail
    backend = Backend()
    results = []
    for row in rows:
        results.append(await run_job(row, backend, model))
        print(json.dumps(results[-1]), flush=True)
    profile = load_config()["models"]["profile"]
    return {"split": "dev", "seed": SEED, "jobs": len(rows), "profile": profile,
            "model": load_config()["models"]["profiles"][profile]["nodes"][node],
            "summary": summarise(results), "results": results,
            "scope": "In-process seed tools (no MCP start-up or GigSim network); real model "
                     "calls including Groq free-tier rate-limit waits.",
            "usd_note": "Not computed: model prices are not set yet.",
            "dead_letter_errors": sorted({e.split(" in organization")[0]
                                          for r in results for e in r["errors"]})}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=8)
    report = asyncio.run(run(parser.parse_args().jobs))
    (RESULTS / "cost_latency_dev.json").write_text(json.dumps(report, indent=2) + "\n",
                                                   encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
