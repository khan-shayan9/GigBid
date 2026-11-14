"""Synthetic client conversations for the conversation graph, with per-message truth kept apart."""

import json
import random
from typing import Any

from data.pipeline.common import SOURCE_SYNTHETIC
from data.pipeline.past_proposals import PERSONA_DOMAINS
from data.pipeline.synthetic_jobs import TEMPLATE_DIR

CONVERSATIONS_PER_PERSONA = 20
INTENT_WEIGHTS = {"question": 35, "negotiation": 25, "interview_request": 25, "scam_signal": 15}
INJECTED_MESSAGE_RATE = 0.1
MESSAGE_INJECTION_FAMILIES = ["ignore_instructions", "auto_submit", "exfiltrate"]
TITLE_CHARS = 60


def build_conversations(
    rng: random.Random,
    jobs: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
    splits: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    messages_by_intent = json.loads((TEMPLATE_DIR / "messages.json").read_text("utf-8"))["intents"]
    injections = json.loads((TEMPLATE_DIR / "injections.json").read_text("utf-8"))["families"]
    real_by_domain: dict[str, list[dict[str, Any]]] = {}
    kinds = {note["job_id"]: note for note in annotations}
    # an injection family held out for jobs stays out of dev conversations too
    heldout_families = {note["family"] for note in annotations
                        if note["kind"] == "injection" and splits[note["job_id"]] == "heldout"}
    for job in jobs:
        note = kinds[job["job_id"]]
        if note["kind"] == "real":
            real_by_domain.setdefault(note["domain"], []).append(job)

    conversations, truth = [], []
    intents, weights = list(INTENT_WEIGHTS), list(INTENT_WEIGHTS.values())
    for persona_id, domain in PERSONA_DOMAINS.items():
        for number, job in enumerate(
            rng.sample(real_by_domain[domain], CONVERSATIONS_PER_PERSONA), start=1
        ):
            conversation_id = f"{persona_id}-conv-{number:02d}"
            split = splits[job["job_id"]]
            families = [family for family in MESSAGE_INJECTION_FAMILIES
                        if split == "heldout" or family not in heldout_families]
            messages, minute = [], 0
            for index in range(rng.randint(1, 3)):
                intent = rng.choices(intents, weights)[0]
                text = rng.choice(messages_by_intent[intent]).format(
                    title=job["title"][:TITLE_CHARS].strip()
                )
                family = None
                if rng.random() < INJECTED_MESSAGE_RATE:
                    family = rng.choice(families)
                    text = f"{text} {rng.choice(injections[family])}"
                minute += rng.randint(30, 1440)
                message_id = f"{conversation_id}-m{index + 1}"
                messages.append({"message_id": message_id, "from": "client", "text": text,
                                 "sent_after_min": minute})
                truth.append({"message_id": message_id, "source": SOURCE_SYNTHETIC,
                              "conversation_id": conversation_id, "split": split,
                              "intent": intent, "injection_family": family})
            conversations.append({
                "conversation_id": conversation_id, "source": SOURCE_SYNTHETIC,
                "persona_id": persona_id, "job_id": job["job_id"],
                "client_id": job["client_id"], "messages": messages,
            })
    return conversations, truth
