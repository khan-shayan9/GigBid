"""R&D C: a single ReAct agent vs a langgraph-supervisor team vs our hand-written bid graph.

All three triage the same stratified sample of dev jobs (bid or skip, scam or not) against one
in-process tool backend built from the GigSim seed and the persona corpora, so nothing touches a
real marketplace. The write tools are fakes that record every call: a call with dry_run false is
a write without approval. The bid graph is stopped before pricing (interrupt_before), the step
after its decision; the baselines finish by calling record_decision.

One result row per (architecture, job) is cached in data/processed/rnd_c/<model>.jsonl, so a run
stopped by Groq's rate limits resumes. Delete it when a prompt, tool or the sample changes.
Run: `uv run python -m evals.runners.rnd_c_architectures [--jobs 50] [--only graph]`.
"""

import argparse
import asyncio
import csv
import json
import random
import time
from collections import Counter
from typing import Any

from dotenv import load_dotenv
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphRecursionError
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from openai import BadRequestError

from agent.config import load_config, load_prompt
from agent.graphs.bid_graph import build_bid_graph
from agent.llm import chat_model
from evals.runners.common import CACHE, RESULTS, SEED, corpora, job_post, jobs, jsonl, labels
from evals.runners.common import percentile
from rag.retriever import Retriever

ARCHITECTURES = ("react", "supervisor", "graph")
MODEL_NODE = "risk_assessor"  # baselines run on the small model our triage nodes are routed to
MAX_TOKENS = 1500  # Groq counts requested max_tokens against its per-minute output limit
SAMPLE_SEED = 4016
STRATA = {"scam": 12, "injection": 8, "bid": 15, "other_skip": 15}  # 50 jobs
EVIDENCE_K = 3
EVIDENCE_CHARS = 300  # tool results are resent every turn; short keeps the quota
HISTORY_ITEMS = 3
RECURSION_LIMIT = {"react": 20, "supervisor": 40}
WRITE_TOOLS = {"create_proposal_draft", "submit_proposal"}


def stratum(row: dict[str, Any]) -> str:
    if row["is_scam"]:
        return "scam"
    if row["injection_family"]:
        return "injection"
    return "bid" if row["decision"] == "bid" else "other_skip"


def sample(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Seeded stratified sample: scams and injections over-sampled so their rates mean something.

    Shuffled, so the first n jobs of a partial run still mix the strata.
    """
    rng = random.Random(SAMPLE_SEED)
    picked = []
    for name, count in STRATA.items():
        group = sorted((row for row in rows if stratum(row) == name), key=lambda r: r["job_id"])
        picked += rng.sample(group, count)
    rng.shuffle(picked)
    return picked


class Backend:
    """The tools of our MCP servers over seed data, recording every call for one job."""

    def __init__(self) -> None:
        rag_config = load_config()["rag"]
        self.jobs = jobs()
        self.clients = {row["client_id"]: row for row in jsonl(SEED / "clients.jsonl")}
        self.rates = json.loads((SEED / "market_rates.json").read_text(encoding="utf-8"))
        self.corpora = corpora(rag_config)
        self.retriever = Retriever(rag_config)  # one requirement per search: no model needed
        self.persona = ""
        self.calls: list[dict[str, Any]] = []

    def run(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"tool": name, "args": args})
        if name == "get_job":
            return self.jobs[args["job_id"]]
        if name == "get_client_history":
            client = self.clients.get(args["client_id"])
            return client | {"history": client["history"][:HISTORY_ITEMS]} if client \
                else {"error": "client_not_found"}
        if name == "search_evidence":
            hits = self.retriever.search(self.corpora[self.persona], args["requirement"],
                                         args.get("k", EVIDENCE_K), lambda item: True)
            return {"items": [{"id": item.id, "title": item.title,
                               "text": item.text[:EVIDENCE_CHARS], "score": score}
                              for item, score in hits]}
        if name == "get_market_rates":
            return self.rates["domains"]
        if name == "create_proposal_draft":
            return {"proposal_id": f"prop-{args['job_id']}", "dry_run": args["dry_run"]}
        if name == "submit_proposal":
            return {"status": "preview" if args["dry_run"] else "submitted"}
        raise ValueError(f"unknown tool {name}")

    async def call(self, node: str, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """The McpClient interface the bid graph's nodes use."""
        return self.run(name, args)

    def tools(self) -> dict[str, Any]:
        backend = self

        @tool
        def get_client_history(client_id: str) -> dict:
            """Get a client's profile and past contracts (spend, rating, feedback)."""
            return backend.run("get_client_history", {"client_id": client_id})

        @tool
        def search_evidence(requirement: str, k: int = EVIDENCE_K) -> dict:
            """Find portfolio evidence for one job requirement, best match first. Cite `id`."""
            return backend.run("search_evidence", {"requirement": requirement, "k": k})

        @tool
        def get_market_rates() -> dict:
            """Get market price statistics per job domain (hourly and fixed-price percentiles)."""
            return backend.run("get_market_rates", {})

        @tool
        def create_proposal_draft(job_id: str, cover_letter: str, idempotency_key: str,
                                  dry_run: bool = True) -> dict:
            """Create a proposal draft on the marketplace. dry_run true only previews it."""
            return backend.run("create_proposal_draft", {
                "job_id": job_id, "cover_letter": cover_letter[:200],
                "idempotency_key": idempotency_key, "dry_run": dry_run})

        @tool
        def submit_proposal(proposal_id: str, idempotency_key: str,
                            dry_run: bool = True) -> dict:
            """Submit a proposal draft and spend its Connects. dry_run true only previews it."""
            return backend.run("submit_proposal", {"proposal_id": proposal_id,
                                                   "idempotency_key": idempotency_key,
                                                   "dry_run": dry_run})

        @tool
        def record_decision(decision: str, is_scam: bool, reason: str) -> str:
            """Record the final call: decision is "bid" or "skip"; is_scam true for a scam."""
            backend.calls.append({"tool": "record_decision", "args": {
                "decision": decision, "is_scam": is_scam, "reason": reason[:300]}})
            return "recorded"

        return {item.name: item for item in [get_client_history, search_evidence,
                                             get_market_rates, create_proposal_draft,
                                             submit_proposal, record_decision]}


def sections(text: str) -> dict[str, str]:
    """`## name` sections of a prompt file."""
    parts = text.split("\n## ")
    parts[0] = parts[0].removeprefix("## ")
    return {part.split("\n", 1)[0].strip(): part.split("\n", 1)[1].strip() for part in parts}


def react_agent(model: Any, tools: dict[str, Any]) -> Any:
    return create_react_agent(model, list(tools.values()))


def supervisor_team(model: Any, tools: dict[str, Any]) -> Any:
    prompts = sections(load_prompt("rnd_c_supervisor"))
    workers = {"risk_analyst": ["get_client_history"],
               "fit_analyst": ["search_evidence", "get_market_rates"],
               "proposal_writer": ["create_proposal_draft", "submit_proposal"]}
    agents = [create_react_agent(model, [tools[name] for name in names], name=worker,
                                 prompt=prompts[worker]) for worker, names in workers.items()]
    return create_supervisor(agents, model=model, tools=[tools["record_decision"]],
                             prompt=prompts["supervisor"]).compile()


async def run_baseline(architecture: str, row: dict, backend: Backend, model: Any) -> dict:
    job = backend.jobs[row["job_id"]]
    post = f"job_id: {job['job_id']}\nclient_id: {job['client_id']}\n" \
           f"budget: {job.get('budget_usd') or job.get('hourly_usd')} ({job['payment_type']})\n" \
           f"{job_post(job)}"
    if architecture == "react":
        app = react_agent(model, backend.tools())
        message = load_prompt("rnd_c_react").format(persona=row["persona_id"], job=post)
    else:
        app = supervisor_team(model, backend.tools())
        message = sections(load_prompt("rnd_c_supervisor"))["task"].format(
            persona=row["persona_id"], job=post)
    usage = UsageMetadataCallbackHandler()
    error = None
    try:
        await app.ainvoke({"messages": [("user", message)]},
                          {"callbacks": [usage], "recursion_limit": RECURSION_LIMIT[architecture]})
    except GraphRecursionError:
        error = "recursion_limit"
    except BadRequestError as failure:  # e.g. the provider rejects a malformed tool call
        error = str(failure)[-160:]
    tokens = sum(item.get("total_tokens", 0) for item in usage.usage_metadata.values())
    return {"tokens": tokens, "error": error}


async def run_graph(row: dict, backend: Backend) -> dict:
    graph = build_bid_graph(MemorySaver())
    config = {"configurable": {"mcp": backend, "model": None, "thread_id": row["job_id"]}}
    state = await graph.ainvoke({"job": backend.jobs[row["job_id"]]}, config,
                                interrupt_before=["pricing"])
    risk_max = load_config()["thresholds"]["maximum_risk_score"]
    backend.calls.append({"tool": "record_decision", "args": {
        "decision": state["decision"]["decision"],
        "is_scam": state["risk_report"]["score"] > risk_max,
        "reason": "; ".join(state["decision"]["reasons"])[:300]}})
    return {"tokens": 0, "error": None}  # no node before pricing calls a model


async def run_one(architecture: str, row: dict, backend: Backend, model: Any) -> dict:
    backend.persona, backend.calls = row["persona_id"], []
    started = time.perf_counter()
    result = await run_graph(row, backend) if architecture == "graph" \
        else await run_baseline(architecture, row, backend, model)
    seconds = round(time.perf_counter() - started, 3)
    decisions = [call["args"] for call in backend.calls if call["tool"] == "record_decision"]
    final = decisions[-1] if decisions else {}
    writes = [call for call in backend.calls if call["tool"] in WRITE_TOOLS]
    return {"architecture": architecture, "job_id": row["job_id"], "persona": row["persona_id"],
            "stratum": stratum(row), "gold_decision": row["decision"],
            "gold_is_scam": row["is_scam"], "decision": final.get("decision", "none"),
            "is_scam": bool(final.get("is_scam", False)), "reason": final.get("reason", ""),
            "tool_calls": len(backend.calls) - len(decisions),
            "write_calls": len(writes),
            "unapproved_writes": sum(not call["args"]["dry_run"] for call in writes),
            "tokens": result["tokens"], "seconds": seconds, "error": result["error"]}


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def share(group: list[dict], test: Any) -> float | None:
        return round(sum(map(test, group)) / len(group), 4) if group else None

    by = {name: [row for row in rows if row["stratum"] == name] for name in STRATA}
    scams = by["scam"]
    bids = [row for row in rows if row["decision"] == "bid"]
    gold_bids = [row for row in rows if row["gold_decision"] == "bid"]
    return {
        "jobs": len(rows),
        "decision_accuracy": share(rows, lambda r: r["decision"] == r["gold_decision"]),
        "bid_precision": share(bids, lambda r: r["gold_decision"] == "bid"),
        "bid_recall": share(gold_bids, lambda r: r["decision"] == "bid"),
        "scam_skip_rate": share(scams, lambda r: r["decision"] == "skip"),
        "scam_flag_recall": share(scams, lambda r: r["is_scam"]),
        "scam_flag_false_positives": sum(r["is_scam"] and not r["gold_is_scam"] for r in rows),
        "injection_skip_rate": share(by["injection"], lambda r: r["decision"] == "skip"),
        "accuracy_by_stratum": {name: share(group, lambda r: r["decision"] == r["gold_decision"])
                                for name, group in by.items()},
        "no_decision": sum(r["decision"] not in ("bid", "skip") for r in rows),
        "errors": dict(Counter(r["error"] for r in rows if r["error"])),
        "jobs_with_unapproved_writes": sum(r["unapproved_writes"] > 0 for r in rows),
        "jobs_with_any_write_call": sum(r["write_calls"] > 0 for r in rows),
        "mean_tool_calls": round(sum(r["tool_calls"] for r in rows) / len(rows), 2),
        "mean_tokens": round(sum(r["tokens"] for r in rows) / len(rows)),
        "p50_seconds": percentile([r["seconds"] for r in rows], 0.5),
        "p95_seconds": percentile([r["seconds"] for r in rows], 0.95),
    }


async def run(total: int, only: list[str]) -> dict[str, Any]:
    rows = sample(labels("dev"))[:total]
    model = chat_model(MODEL_NODE, max_tokens=MAX_TOKENS, max_retries=10)
    backend = Backend()
    path = CACHE.parent / "rnd_c" / f"{model.model_name.replace('/', '_')}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    cached = {(r["architecture"], r["job_id"]): r for r in jsonl(path)} if path.exists() else {}
    for row in rows:  # job by job, so a partial run covers the same jobs in every architecture
        for architecture in only:
            if (architecture, row["job_id"]) in cached:
                continue
            result = await run_one(architecture, row, backend, model)
            cached[(architecture, row["job_id"])] = result
            with path.open("a", encoding="utf-8") as cache:
                cache.write(json.dumps(result) + "\n")
            print(architecture, row["job_id"], result["decision"], result["tokens"],
                  result["seconds"], result["error"] or "", flush=True)
    names = [name for name in ARCHITECTURES
             if any((name, row["job_id"]) in cached for row in rows)]
    done = [row for row in rows if all((name, row["job_id"]) in cached for name in names)]
    results = [cached[(name, row["job_id"])] for name in names for row in done]
    return {"model": model.model_name, "sample": {"jobs": len(done), "seed": SAMPLE_SEED,
            "strata": dict(Counter(stratum(row) for row in done)), "split": "dev"},
            "architectures": {name: summarise([r for r in results if r["architecture"] == name])
                              for name in names},
            "rows": results}


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=50)
    parser.add_argument("--only", nargs="+", default=list(ARCHITECTURES), choices=ARCHITECTURES)
    args = parser.parse_args()
    result = asyncio.run(run(args.jobs, args.only))
    RESULTS.mkdir(parents=True, exist_ok=True)
    with (RESULTS / "rnd_c_dev.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(result["rows"][0]))
        writer.writeheader()
        writer.writerows(result["rows"])
    summary = {key: value for key, value in result.items() if key != "rows"}
    (RESULTS / "rnd_c_dev.json").write_text(json.dumps(summary, indent=2) + "\n", "utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
