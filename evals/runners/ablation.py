"""R&D B ablation: the shipped pipeline with one component removed at a time (retrieval metrics).

Run: `uv run python -m evals.runners.ablation [--per-persona 20]`
Writes evals/results/rag_ablation_dev.json and .csv (same sample as rag_eval with the same N).
"""

import argparse

from dotenv import load_dotenv

from agent.config import load_config
from evals.runners.rag_eval import evaluate, labels, sample, write


def ablations(name: str, switches: dict[str, bool]) -> dict[str, dict[str, bool]]:
    variants = {name: switches}
    for switch, on in switches.items():
        if on:
            variants[f"{name}-without-{switch}"] = switches | {switch: False}
    if switches.get("corrective"):  # corrective grades with reranker scores, so it needs both
        variants.pop(f"{name}-without-rerank", None)
    return variants


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-persona", type=int, default=20)
    parser.add_argument("--pipeline", help="variant to ablate (default: the shipped rag.variant)")
    args = parser.parse_args()
    rag = load_config()["rag"]
    name = args.pipeline or rag["variant"]
    variants = ablations(name, rag["variants"][name])
    result = evaluate(variants, sample(labels("dev"), args.per_persona))
    write(result | {"split": "dev", "per_persona": args.per_persona}, "rag_ablation_dev")


if __name__ == "__main__":
    main()
