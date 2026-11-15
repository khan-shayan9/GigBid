"""B4 retrieval: evidence Recall@5, MRR and nDCG@10 for each variant, by persona and job type.

Gold evidence (evals/datasets/<split>.jsonl) names case studies, so results are scored per
project: each retrieved item counts as its project (a review counts as the case study it
reviews; a repo or CV section counts as itself), and repeats of a project are dropped.
Jobs with no gold evidence are not scored for recall; they measure refusals instead (V8).

Run: `uv run python -m evals.runners.rag_eval [--split dev] [--variants v0,v2] [--per-persona N]`
Writes evals/results/rag_retrieval_<split>.json and .csv.
"""

import argparse
import csv
import hashlib
import json
import math
import time
from collections.abc import Callable
from typing import Any

from dotenv import load_dotenv

from agent.config import load_config, load_prompt
from evals.runners.common import (
    PERSONA_DOMAIN,
    RESULTS,
    CachedModel,
    CachedReranker,
    annotations,
    corpora,
    job_post,
    jobs,
    labels,
    percentile,
)
from rag.ingest.portfolio import EvidenceItem
from rag.retriever import Retriever, VariantSettings

RETRIEVE_ITEMS = 20  # items fetched per job, so 10 distinct projects remain after dropping repeats
EVIDENCE_TYPES = {"case_study", "cv", "repo", "review"}  # search_evidence's default filter
MANY_REQUIREMENTS = 4  # the R&D B hypothesis splits jobs at four or more listed skills
METRICS = ("recall_at_5", "mrr", "ndcg_at_10")


def units(hits: list[tuple[EvidenceItem, float]]) -> list[str]:
    """Retrieved projects in rank order, each once."""
    return list(dict.fromkeys(item.project or item.id for item, _ in hits))


def recall_at(ranked: list[str], gold: set[str], k: int) -> float:
    return len(set(ranked[:k]) & gold) / len(gold)


def reciprocal_rank(ranked: list[str], gold: set[str]) -> float:
    return next((1 / rank for rank, unit in enumerate(ranked, start=1) if unit in gold), 0.0)


def ndcg_at(ranked: list[str], gold: set[str], k: int) -> float:
    gain = sum(1 / math.log2(rank + 1) for rank, unit in enumerate(ranked[:k], start=1)
               if unit in gold)
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(len(gold), k) + 1))
    return gain / ideal


def sample(rows: list[dict[str, Any]], per_persona: int | None) -> list[dict[str, Any]]:
    """Up to N jobs with gold evidence per persona (a fixed hash order), plus every job without."""
    if not per_persona:
        return rows
    order = sorted(rows, key=lambda row: hashlib.sha256(row["job_id"].encode()).hexdigest())
    kept = [row for row in order if not row["relevant_evidence_ids"]]
    for persona in PERSONA_DOMAIN:
        kept += [row for row in order
                 if row["persona_id"] == persona and row["relevant_evidence_ids"]][:per_persona]
    return sorted(kept, key=lambda row: (row["persona_id"], row["job_id"]))


def mean_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if row["gold"]]
    summary: dict[str, Any] = {"jobs": len(scored)}
    for metric in METRICS:
        summary[metric] = round(sum(row[metric] for row in scored) / len(scored), 4) \
            if scored else None
    return summary


def grouped(rows: list[dict[str, Any]], key: Callable[[dict[str, Any]], Any]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(key(row)), []).append(row)
    return {name: mean_metrics(members) for name, members in sorted(groups.items())}


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    no_gold = [row for row in rows if not row["gold"]]
    with_gold = [row for row in rows if row["gold"]]
    return {
        "overall": mean_metrics(rows),
        "by_persona": grouped(rows, lambda row: row["persona"]),
        "by_kind": grouped(rows, lambda row: row["kind"]),
        "by_domain": grouped(rows, lambda row: "own" if row["own_domain"] else "off"),
        "by_requirements": grouped(rows, lambda row: f">={MANY_REQUIREMENTS}"
                                   if row["skills"] >= MANY_REQUIREMENTS
                                   else f"<{MANY_REQUIREMENTS}"),
        "latency_s": {"p50": percentile([row["seconds"] for row in rows], 0.5),
                      "p95": percentile([row["seconds"] for row in rows], 0.95)},
        "refusal": {"no_gold_jobs": len(no_gold),
                    "refused_without_gold": sum(row["refused"] for row in no_gold),
                    "refused_with_gold": sum(row["refused"] for row in with_gold)},
    }


def evaluate(variants: dict[str, dict[str, bool]], rows: list[dict[str, Any]],
             log: Callable[[str], None] = print) -> dict[str, Any]:
    """Score each named variant (a dict of switches) on the given label rows."""
    config = load_config()
    rag_config = config["rag"] | {"variants": variants}
    persona_corpora = corpora(rag_config)
    all_jobs, notes = jobs(), annotations()
    reranker = CachedReranker()
    model = CachedModel("rag_query", "rag_query")
    prompts = {"decompose": load_prompt("rag_decompose"), "rewrite": load_prompt("rag_rewrite")}
    results: dict[str, Any] = {}
    for name, switches in variants.items():
        settings = VariantSettings(**switches)
        retriever = Retriever(rag_config, name, reranker=reranker, complete=model, prompts=prompts)
        scored = []
        for number, row in enumerate(rows, start=1):
            job, gold = all_jobs[row["job_id"]], set(row["relevant_evidence_ids"])
            started = time.perf_counter()
            hits = retriever.search_job(persona_corpora[row["persona_id"]], job_post(job),
                                        RETRIEVE_ITEMS, lambda item: item.type in EVIDENCE_TYPES)
            seconds = time.perf_counter() - started
            ranked = units(hits)
            scored.append({
                "variant": name, "persona": row["persona_id"], "job_id": row["job_id"],
                "kind": notes[row["job_id"]]["kind"], "skills": len(job["skills"]),
                "own_domain": notes[row["job_id"]]["domain"] == PERSONA_DOMAIN[row["persona_id"]],
                "gold": sorted(gold), "retrieved": ranked[:10], "refused": not hits,
                "seconds": round(seconds, 4),
                **({"recall_at_5": recall_at(ranked, gold, 5),
                    "mrr": reciprocal_rank(ranked, gold),
                    "ndcg_at_10": ndcg_at(ranked, gold, 10)} if gold else {})})
            if number % 50 == 0:
                log(f"{name}: {number}/{len(rows)} jobs")
        results[name] = {"switches": settings.model_dump(), **summarise(scored), "rows": scored}
        log(f"{name}: {results[name]['overall']}")
    return {"config": {key: rag_config[key] for key in
                       ("chunk_words", "chunk_overlap", "candidates", "rerank_depth", "rrf_k",
                        "corrective")}
            | {"embedder": config["models"]["embeddings"]["model"],
               "reranker": reranker.model_id, "rag_query_model": model.model.model_name},
            "jobs": len(rows), "variants": results}


def write(result: dict[str, Any], name: str) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{name}.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    with (RESULTS / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["variant", "group", "value", "jobs", *METRICS])
        for variant, data in result["variants"].items():
            writer.writerow([variant, "overall", "all", data["overall"]["jobs"],
                             *(data["overall"][metric] for metric in METRICS)])
            for group in ("by_persona", "by_kind", "by_domain", "by_requirements"):
                for value, summary in data[group].items():
                    writer.writerow([variant, group, value, summary["jobs"],
                                     *(summary[metric] for metric in METRICS)])


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev", choices=["dev", "heldout"])
    parser.add_argument("--variants", help="comma-separated names from rag.variants")
    parser.add_argument("--per-persona", type=int, help="jobs with gold evidence per persona")
    args = parser.parse_args()
    configured = load_config()["rag"]["variants"]
    names = args.variants.split(",") if args.variants else list(configured)
    rows = sample(labels(args.split), args.per_persona)
    # Variants already scored on the same split and sample are kept; rerun ones are replaced.
    previous = RESULTS / f"rag_retrieval_{args.split}.json"
    result: dict[str, Any] = json.loads(previous.read_text(encoding="utf-8")) \
        if previous.exists() else {}
    if result.get("per_persona") != args.per_persona:
        result = {}
    for name in names:  # written after each variant, so a crash keeps what finished
        done = evaluate({name: configured[name]}, rows)
        result = done | {"variants": result.get("variants", {}) | done["variants"]}
        write(result | {"split": args.split, "per_persona": args.per_persona},
              f"rag_retrieval_{args.split}")


if __name__ == "__main__":
    main()
