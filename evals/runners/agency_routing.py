"""X1 agency mode: does the router send a job to the member it suits? (docs/EXTENSION.md)

    uv run python -m evals.runners.agency_routing

Runs the shipped Fit Matcher for every persona on each dev job and the shipped router
(`agent/nodes/router.py`), over seed data and the shipped retrieval variant; no LLM calls.

Gold: no dev job is labelled bid for two personas, so a job labelled bid for persona P counts
as "P is right". This checks agreement with how data/pipeline/ assigned jobs to personas, not
whether another member could also have done the job; pairs with no label are unknown, not skip.
`contrast` is the jobs labelled bid for one persona and skip for another.

`decisions` asks what routing does to bid or skip (the decision node, run as in
rnd_c_architectures.run_graph, no LLM): one persona per account, each labelled (job, persona)
pair decided as that persona, against agency mode, each dev job decided as its routed member and
counted as a team bid when any persona is labelled bid. Unlabelled pairs make the team gold a
lower bound. Dev split only.
"""

import asyncio
import json
from collections import defaultdict

from langgraph.checkpoint.memory import MemorySaver

from agent.config import load_config
from agent.graphs.bid_graph import build_bid_graph
from agent.nodes.router import fit_for, route
from evals.runners.common import RESULTS, labels
from evals.runners.rnd_c_architectures import Backend


def _accuracy(hits: list[bool]) -> dict:
    return {"n": len(hits), "accuracy": round(sum(hits) / len(hits), 3) if hits else None}


def _bid_scores(pairs: list[tuple[bool, bool]]) -> dict:
    """(predicted bid, gold bid) pairs -> bid precision, recall and F1."""
    true_pos = sum(pred and gold for pred, gold in pairs)
    predicted, actual = sum(pred for pred, _ in pairs), sum(gold for _, gold in pairs)
    precision = true_pos / predicted if predicted else 0.0
    recall = true_pos / actual if actual else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"n": len(pairs), "gold_bids": actual, "predicted_bids": predicted,
            "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


async def _bids(backend: Backend, graph: object, job_id: str, member: str) -> bool:
    backend.persona = member
    config = {"configurable": {"mcp": backend, "model": None,
                               "thread_id": f"{member}:{job_id}"}}
    state = await graph.ainvoke({"job": backend.jobs[job_id]}, config,
                                interrupt_before=["pricing"])
    return state["decision"]["decision"] == "bid"


async def _routed(backend: Backend, members: list[str], job_id: str) -> tuple[str, dict]:
    fits = {}
    for member in members:
        backend.persona = member
        fits[member] = await fit_for(backend.jobs[job_id], backend)
    decision = route(fits)
    return decision.member, fits


async def _decisions(backend: Backend, members: list[str], rows: list[dict],
                     decisions: dict) -> dict:
    graph = build_bid_graph(MemorySaver())
    single = [(await _bids(backend, graph, row["job_id"], row["persona_id"]),
               row["decision"] == "bid") for row in rows]
    team = []
    for job_id, found in sorted(decisions.items()):
        member, _ = await _routed(backend, members, job_id)
        team.append((await _bids(backend, graph, job_id, member), "bid" in found.values()))
    return {"single_persona_pairs": _bid_scores(single), "agency_jobs": _bid_scores(team)}


async def run() -> dict:
    backend = Backend()
    members = list(load_config()["api"]["personas"])
    rows = labels("dev")
    decisions = defaultdict(dict)
    for row in rows:
        decisions[row["job_id"]][row["persona_id"]] = row["decision"]
    gold = {job: next(p for p, d in found.items() if d == "bid")
            for job, found in decisions.items() if "bid" in found.values()}
    contrast = {job for job, found in decisions.items()
                if "bid" in found.values() and "skip" in found.values()}
    results = []
    for job_id, persona in sorted(gold.items()):
        _, fits = await _routed(backend, members, job_id)
        decision = route(fits)
        top = max(fit.score for fit in fits.values())
        results.append({"job_id": job_id, "gold": persona, "routed": decision.member,
                        "tied_at_top": sum(fit.score == top for fit in fits.values()) > 1,
                        "fit_scores": decision.fit_scores})
    by_persona = {member: _accuracy([r["routed"] == r["gold"] for r in results
                                     if r["gold"] == member]) for member in members}
    return {
        "split": "dev", "members": members,
        "rag_variant": load_config()["rag"]["variant"],
        "router": _accuracy([r["routed"] == r["gold"] for r in results]),
        "jobs_tied_at_top": sum(r["tied_at_top"] for r in results),
        "router_on_ties": _accuracy([r["routed"] == r["gold"] for r in results
                                     if r["tied_at_top"]]),
        "contrast_jobs": _accuracy([r["routed"] == r["gold"] for r in results
                                    if r["job_id"] in contrast]),
        "baselines": {"random_expected": round(1 / len(members), 3),
                      **{f"always_{member}": _accuracy([r["gold"] == member for r in results])
                         for member in members}},
        "by_gold_persona": by_persona,
        "decisions": await _decisions(backend, members, rows, decisions),
        "results": results,
    }


def main() -> None:
    result = asyncio.run(run())
    (RESULTS / "agency_routing_dev.json").write_text(json.dumps(result, indent=2) + "\n",
                                                     encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    main()
