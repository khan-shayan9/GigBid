"""Assemble each persona's past proposals from authored snippets, with won/replied/ignored labels.

The outcome rule below is label-generation logic: it stays in data/pipeline/ only and is never
copied into agent/ prompts or config.
"""

import json
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from data.pipeline.common import PERSONA_DIR, SOURCE_SYNTHETIC

# Snippets hold the evidence keyword map that gold labels use, so they stay out of data/personas/.
SNIPPET_DIR = Path(__file__).parent / "templates" / "proposal_snippets"
PERSONA_DOMAINS = {"ai_ml_engineer": "ai_ml", "fullstack_dev": "web", "data_analyst": "data"}
PROPOSALS_IN_DOMAIN = 120
PROPOSALS_OFF_DOMAIN = 30
PERSONAL_OPENING_RATE = 0.6
SLOPPY_EVIDENCE_RATE = 0.25  # proposal cites evidence that does not fit the job
TITLE_CHARS = 60
WON_THRESHOLD = 2.0
REPLIED_THRESHOLD = 0.8


def load_snippets(persona_id: str) -> dict[str, Any]:
    return json.loads((SNIPPET_DIR / f"{persona_id}.json").read_text(encoding="utf-8"))


def keyword_hits(keywords: list[str], text: str) -> int:
    return sum(bool(re.search(rf"\b{re.escape(word)}\b", text)) for word in keywords)


def _pick_evidence(
    rng: random.Random, evidence: list[dict[str, Any]], job_text: str
) -> tuple[list[dict[str, Any]], int]:
    """Return the cited evidence and how many of the citations actually match the job."""
    if rng.random() < SLOPPY_EVIDENCE_RATE:
        return [rng.choice(evidence)], 0
    scored = sorted(
        ((keyword_hits(item["keywords"], job_text), index) for index, item in enumerate(evidence)),
        reverse=True,
    )
    relevant = [evidence[index] for hits, index in scored[:2] if hits > 0]
    if not relevant:
        return [rng.choice(evidence)], 0
    return relevant, len(relevant)


def _bid(rng: random.Random, job: dict[str, Any], hourly_rate: float) -> tuple[dict, float]:
    """Return the bid and its ratio to the job's own budget (1.0 when the job has none)."""
    if job["payment_type"] == "hourly":
        top = (job["hourly_usd"] or {}).get("max") or (job["hourly_usd"] or {}).get("min")
        return {"type": "hourly", "amount_usd": hourly_rate}, hourly_rate / top if top else 1.0
    budget = job["budget_usd"]
    if not budget:
        return {"type": "fixed", "amount_usd": hourly_rate * 10}, 1.0
    amount = round(budget * rng.uniform(0.8, 1.4) / 10) * 10 or 10
    return {"type": "fixed", "amount_usd": amount}, amount / budget


def _outcome(rng: random.Random, personal: bool, matches: int, in_domain: bool, ratio: float) -> str:
    score = (
        1.0 * personal
        + 0.8 * (matches > 0)
        + 0.4 * (matches > 1)
        - 0.6 * (not in_domain)
        - 0.5 * (ratio > 1.2)
        + rng.gauss(0, 0.5)
    )
    if score >= WON_THRESHOLD:
        return "won"
    return "replied" if score >= REPLIED_THRESHOLD else "ignored"


def build_past_proposals(
    rng: random.Random, persona_id: str, historical_jobs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    persona_dir = PERSONA_DIR / persona_id
    profile = json.loads((persona_dir / "profile.json").read_text(encoding="utf-8"))
    snippets = load_snippets(persona_id)
    domain = PERSONA_DOMAINS[persona_id]
    own = [job for job in historical_jobs if job["category"] == domain]
    others = [job for job in historical_jobs if job["category"] != domain]
    chosen = rng.sample(own, PROPOSALS_IN_DOMAIN) + rng.sample(others, PROPOSALS_OFF_DOMAIN)
    chosen.sort(key=lambda job: job["posted_at"])

    proposals = []
    for number, job in enumerate(chosen, start=1):
        job_text = f"{job['title']} {job['description']}".lower()
        personal = rng.random() < PERSONAL_OPENING_RATE
        openings = snippets["openings_personal" if personal else "openings_generic"]
        cited, matches = _pick_evidence(rng, snippets["evidence"], job_text)
        bid, ratio = _bid(rng, job, profile["hourly_rate_usd"])
        rate_line = (
            f"My rate is ${bid['amount_usd']:.0f}/hour."
            if bid["type"] == "hourly"
            else f"I can deliver this for ${bid['amount_usd']:.0f} fixed."
        )
        letter = " ".join([
            rng.choice(openings).format(title=job["title"][:TITLE_CHARS].strip()),
            *(item["line"] for item in cited),
            rate_line,
            rng.choice(snippets["closings"]),
        ])
        sent = datetime.strptime(job["posted_at"], "%Y-%m-%dT%H:%M:%SZ")
        sent += timedelta(hours=rng.randint(1, 48))
        proposals.append({
            "proposal_id": f"{persona_id}-prop-{number:03d}",
            "source": SOURCE_SYNTHETIC,
            "persona_id": persona_id,
            "job_id": job["job_id"],
            "sent_at": sent.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "cover_letter": letter,
            "evidence_ids": [item["evidence_id"] for item in cited],
            "bid": bid,
            "outcome": _outcome(rng, personal, matches, job["category"] == domain, ratio),
        })
    return proposals
