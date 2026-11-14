"""Simulated client reaction to a submitted proposal.

Rule mode (default, seeded, used by CI and evals) scores the same factors as the Phase 1
past-proposal rule: a personal opening, must-have skills covered, price against the client's
ceiling, plus the client's reply propensity. LLM mode asks a small open model and falls back to
the rules on any error. Weights, thresholds, delays, reply texts and the prompt are data.
"""

import json
import random
import re
from typing import Any

import httpx

from gigsim.models import Job
from gigsim.settings import Settings

OUTCOMES = ("hired", "interview", "replied", "ignored")
LADDER = {
    "hired": ["viewed", "replied", "interview", "hired"],
    "interview": ["viewed", "replied", "interview", "lost"],
    "replied": ["viewed", "replied", "lost"],
    "ignored": ["viewed", "lost"],
    "scam": ["viewed", "replied"],
}
DELAY_KEY = {"hired": "decision", "lost": "decision"}
MIN_TITLE_WORD = 4


def decide_outcome(
    settings: Settings, prefs: dict[str, Any], job: Job, proposal: dict[str, Any]
) -> str:
    if prefs.get("behaviour") == "scammer":
        return "scam"
    if settings.config.client_sim.mode == "llm" and settings.llm_base_url:
        outcome = _ask_llm(settings, prefs, job, proposal)
        if outcome:
            return outcome
    return _rule_outcome(settings, prefs, job, proposal)


def schedule(settings: Settings, outcome: str, now: float) -> list[tuple[str, float, str | None]]:
    """(event type, sim minute, client message text or None) for each lifecycle step."""
    sim_config = settings.config.client_sim
    replies = sim_config.replies
    steps = []
    for event in LADDER[outcome]:
        at_min = now + getattr(sim_config.delays_min, DELAY_KEY.get(event, event))
        scam_reply = outcome == "scam" and event == "replied"
        text = replies.scam if scam_reply else getattr(replies, event, None)
        steps.append((event, at_min, text))
    return steps


def _rule_outcome(
    settings: Settings, prefs: dict[str, Any], job: Job, proposal: dict[str, Any]
) -> str:
    sim_config = settings.config.client_sim
    weights, thresholds = sim_config.weights, sim_config.thresholds
    rng = random.Random(f"{settings.config.random_seed}|{proposal['proposal_id']}")
    letter = proposal["cover_letter"].lower()
    personal = _is_personal(letter, job.title, sim_config.generic_openings)
    must_haves = [skill.lower() for skill in prefs.get("must_have_skills") or []]
    covered = sum(skill in letter for skill in must_haves)
    score = weights.personal_opening * personal
    if prefs.get("dislikes_generic_opening") and not personal:
        score -= weights.personal_opening
    score += weights.any_must_have * (covered > 0 or not must_haves)
    score += weights.most_must_haves * (covered * 2 >= len(must_haves))
    score += weights.over_budget * _over_budget(prefs, job, proposal)
    score += float(prefs.get("reply_propensity", 0.5)) - 0.5
    score += rng.gauss(0, weights.noise_sd)
    for outcome in ("hired", "interview", "replied"):
        if score >= getattr(thresholds, outcome):
            return outcome
    return "ignored"


def _is_personal(letter: str, title: str, generic_openings: list[str]) -> bool:
    opening = letter[:250]
    if any(opening.startswith(phrase) for phrase in generic_openings):
        return False
    words = [word for word in re.findall(r"[a-z0-9+#]+", title.lower()) if len(word) >= MIN_TITLE_WORD]
    return sum(word in opening for word in words) >= min(2, len(words)) if words else False


def _over_budget(prefs: dict[str, Any], job: Job, proposal: dict[str, Any]) -> bool:
    ceiling = prefs.get("budget_ceiling") or {}
    amount = proposal["bid_amount_usd"]
    if ceiling.get("usd") and ceiling.get("type") == proposal["bid_type"]:
        return amount > ceiling["usd"]
    if proposal["bid_type"] == "fixed" and job.budget_usd:
        return amount > job.budget_usd * 1.2
    hourly_max = job.hourly_usd.max if job.hourly_usd else None
    return bool(proposal["bid_type"] == "hourly" and hourly_max and amount > hourly_max * 1.2)


def _ask_llm(
    settings: Settings, prefs: dict[str, Any], job: Job, proposal: dict[str, Any]
) -> str | None:
    prompt = (
        settings.llm_prompt.replace("{client_prefs}", json.dumps(prefs))
        .replace("{job}", job.model_dump_json())
        .replace("{proposal}", proposal["cover_letter"])
    )
    try:
        response = httpx.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json={"model": settings.llm_model, "temperature": 0,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=20,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        outcome = json.loads(content[content.index("{") : content.rindex("}") + 1])["outcome"]
    except (httpx.HTTPError, KeyError, ValueError, IndexError, TypeError, AttributeError):
        return None
    return outcome if outcome in OUTCOMES else None
