"""Entry point for `make seed`: rebuild every seed, persona and eval file deterministically."""

import random

from data.pipeline.common import EVAL_DIR, PERSONA_DIR, SEED, SEED_DIR, write_json, write_jsonl
from data.pipeline.conversations import build_conversations
from data.pipeline.gold_labels import assign_splits, build_gold_labels
from data.pipeline.past_proposals import PERSONA_DOMAINS, build_past_proposals
from data.pipeline.real_jobs import build_historical_jobs, build_stream_jobs_and_clients
from data.pipeline.real_stats import build_market_rates, build_persona_priors
from data.pipeline.synthetic_jobs import build_synthetic_stream


def main() -> None:
    rng = random.Random(SEED)  # one generator, consumed in a fixed order below
    market_rates, contract_pools = build_market_rates()
    historical = build_historical_jobs(rng)
    real_jobs, real_clients = build_stream_jobs_and_clients(rng, contract_pools)
    proposals = {pid: build_past_proposals(rng, pid, historical) for pid in PERSONA_DOMAINS}
    stream = build_synthetic_stream(rng, real_jobs, real_clients, contract_pools)
    splits = assign_splits(rng, stream["annotations"])
    conversations, message_truth = build_conversations(
        rng, stream["jobs"], stream["annotations"], splits
    )
    labels = build_gold_labels(
        rng, stream["jobs"], stream["clients"], stream["annotations"], market_rates, historical,
        splits,
    )

    write_json(SEED_DIR / "market_rates.json", market_rates)
    write_json(PERSONA_DIR / "priors.json", build_persona_priors())
    outputs = {
        SEED_DIR / "historical_jobs.jsonl": historical,
        SEED_DIR / "jobs.jsonl": stream["jobs"],
        SEED_DIR / "clients.jsonl": stream["clients"],
        SEED_DIR / "client_prefs.jsonl": stream["client_prefs"],
        SEED_DIR / "stream.jsonl": stream["stream"],
        SEED_DIR / "conversations.jsonl": conversations,
        EVAL_DIR / "job_annotations.jsonl": stream["annotations"],
        EVAL_DIR / "message_annotations.jsonl": message_truth,
        EVAL_DIR / "dev.jsonl": [label for label in labels if label["split"] == "dev"],
        EVAL_DIR / "heldout.jsonl": [label for label in labels if label["split"] == "heldout"],
    } | {PERSONA_DIR / pid / "past_proposals.jsonl": rows for pid, rows in proposals.items()}
    for path, records in outputs.items():
        count = write_jsonl(path, records)
        print(f"{path.relative_to(SEED_DIR.parents[1])}: {count} records")


if __name__ == "__main__":
    main()
