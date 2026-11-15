"""B3 and B4 proposal quality: draft, verify, judge and submit to GigSim, per retrieval variant.

For a fixed set of dev jobs labelled "bid" (N per persona, fixed hash order), each variant:
retrieves evidence -> the Writer drafts -> the Verifier grades claims and removes unsupported
ones -> the Verifier grades the cleaned draft again -> the judge scores it -> a fresh GigSim
decides the simulated client's reaction. All model replies are cached (evals/runners/common.py).

Run: `uv run python -m evals.runners.proposal_eval [--variants v0,v2] [--per-persona 10]`
Writes evals/results/proposal_eval_dev.json and .csv.
"""

import argparse
import asyncio
import csv
import json
import re
import time
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage

from agent.config import load_config, load_prompt
from agent.nodes.writer import write_letter
from evals.runners.common import (
    PERSONAS,
    RESULTS,
    CachedModel,
    CachedReranker,
    corpora,
    job_post,
    jobs,
    labels,
    percentile,
)
from evals.runners.gigsim_outcomes import outcomes, rates
from evals.runners.rag_eval import EVIDENCE_TYPES, sample
from rag.retriever import Retriever
from rag.verify import VerificationFailed, count_labels, remove_unsupported, verify_claims

EVIDENCE_K = 6  # evidence items the writer sees
JUDGE_SCORE = re.compile(r"\{[^{}]*\"score\"[^{}]*\}")


class CachedChat:
    """Gives the writer's `ainvoke` a cached model, so reruns cost no tokens."""

    def __init__(self, cached: CachedModel) -> None:
        self.cached = cached

    async def ainvoke(self, messages: list[Any]) -> AIMessage:
        row = await asyncio.to_thread(self.cached.call, str(messages[0].content))
        return AIMessage(row["reply"])


def bid_for(job: dict[str, Any], persona: str) -> dict[str, Any]:
    """shortcut: the persona's hourly rate, or the posted fixed budget; the Pricing Strategist
    replaces this in Phase 5. Every variant bids the same, so the comparison is fair."""
    profile = json.loads((PERSONAS / persona / "profile.json").read_text(encoding="utf-8"))
    if job["payment_type"] == "hourly" or not job.get("budget_usd"):
        return {"type": "hourly", "amount_usd": float(profile["hourly_rate_usd"])}
    return {"type": "fixed", "amount_usd": float(job["budget_usd"])}


def judge_score(reply: str) -> int | None:
    match = next(iter(JUDGE_SCORE.findall(reply)[::-1]), None)  # the last JSON object wins
    try:
        score = int(json.loads(match)["score"]) if match else None
    except (ValueError, TypeError, KeyError):
        return None
    return score if score in range(1, 6) else None


def cost(calls: list[dict[str, Any]], prices: dict[str, dict[str, float]]) -> dict[str, Any]:
    tokens_in = sum(call["input_tokens"] for call in calls)
    tokens_out = sum(call["output_tokens"] for call in calls)
    priced = all(call["model"] in prices for call in calls)
    usd = sum(call["input_tokens"] * prices[call["model"]]["input"]
              + call["output_tokens"] * prices[call["model"]]["output"]
              for call in calls) / 1e6 if priced else None
    return {"input_tokens": tokens_in, "output_tokens": tokens_out,
            "usd": round(usd, 6) if usd is not None else None}


async def run_variant(name: str, retriever: Retriever, rows: list[dict[str, Any]],
                      persona_corpora: dict, all_jobs: dict, models: dict[str, CachedModel],
                      prices: dict) -> list[dict[str, Any]]:
    writer, verifier, judge = models["writer"], models["verifier"], models["judge"]
    verify_prompt, judge_prompt = load_prompt("verifier"), load_prompt("judge")
    results = []
    for row in rows:
        job, persona = all_jobs[row["job_id"]], row["persona_id"]
        start_calls = {model: len(cached.log) for model, cached in models.items()}
        started = time.perf_counter()
        hits = retriever.search_job(persona_corpora[persona], job_post(job), EVIDENCE_K,
                                    lambda item: item.type in EVIDENCE_TYPES)
        retrieval_s = time.perf_counter() - started
        evidence = {item.id: item.model_dump() for item, _ in hits}
        draft, _ = await write_letter(job, evidence, CachedChat(writer))  # type: ignore[arg-type]
        try:
            before = verify_claims(draft.cover_letter, list(evidence.values()), verifier,
                                   verify_prompt)
            final = remove_unsupported(draft.cover_letter, before)
            after = verify_claims(final, list(evidence.values()), verifier, verify_prompt) \
                if final else []
            failed = False
        except VerificationFailed:
            before, after, final, failed = [], [], draft.cover_letter, True
        listing = "\n\n".join(f"[{item['id']}] {item['title']}\n{item['text'][:600]}"
                              for item in evidence.values())
        verdict = judge.call(judge_prompt.format(job_post=job_post(job), letter=final,
                                                 evidence=listing))["reply"]
        calls = [call for model, cached in models.items()
                 for call in cached.log[start_calls[model]:]]
        results.append({
            "variant": name, "persona": persona, "job_id": row["job_id"],
            "evidence_ids": list(evidence), "draft": draft.cover_letter, "final": final,
            "verification_failed": failed,
            "before": count_labels(before), "after": count_labels(after),
            "judge_score": judge_score(verdict),
            "seconds": round(retrieval_s + sum(call["seconds"] for call in calls), 3),
            **cost(calls, prices), "bid": bid_for(job, persona)})
        print(f"{name} {persona} {row['job_id']}: {results[-1]['before']} -> "
              f"{results[-1]['after']}, judge {results[-1]['judge_score']}", flush=True)
    for result, outcome in zip(results, outcomes([
            {"persona": r["persona"], "key": f"{r['persona']}-{r['job_id']}",
             "job_id": r["job_id"], "cover_letter": r["final"], "bid": r["bid"]}
            for r in results]), strict=True):
        result["outcome"] = outcome
    return results


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def per_proposal(field: str, label: str) -> float:
        return round(sum(row[field][label] for row in rows) / len(rows), 3)

    def rate(field: str) -> float | None:
        claims = sum(sum(row[field].values()) for row in rows)
        return round(sum(row[field]["unsupported"] for row in rows) / claims, 4) if claims \
            else None

    scores = [row["judge_score"] for row in rows if row["judge_score"] is not None]
    usd = [row["usd"] for row in rows]
    return {
        "proposals": len(rows),
        "unsupported_per_proposal": {"before": per_proposal("before", "unsupported"),
                                     "after": per_proposal("after", "unsupported")},
        "unsupported_claim_rate": {"before": rate("before"), "after": rate("after")},
        "verification_failed": sum(row["verification_failed"] for row in rows),
        "judge_score": round(sum(scores) / len(scores), 3) if scores else None,
        "judge_unparsed": len(rows) - len(scores),
        "gigsim": rates([row["outcome"] for row in rows]),
        "latency_s": {"p50": percentile([row["seconds"] for row in rows], 0.5),
                      "p95": percentile([row["seconds"] for row in rows], 0.95)},
        "tokens_per_proposal": round(sum(row["input_tokens"] + row["output_tokens"]
                                         for row in rows) / len(rows)),
        "usd_per_proposal": round(sum(usd) / len(usd), 6) if None not in usd else None,
    }


async def evaluate(names: list[str], per_persona: int) -> dict[str, Any]:
    config = load_config()
    rag_config = config["rag"]
    rows = [row for row in sample([row for row in labels("dev") if row["decision"] == "bid"],
                                  per_persona) if row["relevant_evidence_ids"]]
    persona_corpora, all_jobs = corpora(rag_config), jobs()
    models = {node: CachedModel(node, node) for node in ("writer", "verifier", "judge")}
    query_model = CachedModel("rag_query", "rag_query")
    prompts = {"decompose": load_prompt("rag_decompose"), "rewrite": load_prompt("rag_rewrite")}
    reranker = CachedReranker()
    prices = config["models"].get("prices_usd_per_million") or {}
    variants: dict[str, Any] = {}
    for name in names:
        retriever = Retriever(rag_config, name, reranker=reranker, complete=query_model,
                              prompts=prompts)
        results = await run_variant(name, retriever, rows, persona_corpora, all_jobs, models,
                                    prices)
        variants[name] = {"overall": summarise(results),
                          "by_persona": {persona: summarise([r for r in results
                                                             if r["persona"] == persona])
                                         for persona in sorted({r["persona"] for r in results})},
                          "rows": results}
    return {"split": "dev", "per_persona": per_persona, "jobs": len(rows),
            "models": {node: model.model.model_name for node, model in models.items()},
            "note": "the rag_query model's tokens (V1, V8) are counted in rag_retrieval, not here",
            "variants": variants}


def write(result: dict[str, Any]) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "proposal_eval_dev.json").write_text(json.dumps(result, indent=1) + "\n",
                                                    encoding="utf-8")
    with (RESULTS / "proposal_eval_dev.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["variant", "persona", "proposals", "unsupported_before",
                         "unsupported_after", "judge_score", "reply_rate", "hire_rate",
                         "p95_latency_s", "usd_per_proposal"])
        for name, data in result["variants"].items():
            for persona, summary in [("all", data["overall"]), *data["by_persona"].items()]:
                writer.writerow([name, persona, summary["proposals"],
                                 summary["unsupported_per_proposal"]["before"],
                                 summary["unsupported_per_proposal"]["after"],
                                 summary["judge_score"], summary["gigsim"]["reply_rate"],
                                 summary["gigsim"]["hire_rate"], summary["latency_s"]["p95"],
                                 summary["usd_per_proposal"]])


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", help="default: v0 and the shipped rag.variant")
    parser.add_argument("--per-persona", type=int, default=10)
    args = parser.parse_args()
    shipped = load_config()["rag"]["variant"]
    names = args.variants.split(",") if args.variants else list(dict.fromkeys(["v0", shipped]))
    write(asyncio.run(evaluate(names, args.per_persona)))


if __name__ == "__main__":
    main()
