"""The rule-based client responds to its inputs, is seeded, and LLM mode falls back to rules."""

from pathlib import Path

import httpx

from gigsim.client_sim import decide_outcome
from gigsim.models import Job
from tests.integration.test_gigsim_reads import make_settings

JOB = Job(job_id="j1", title="Customer support chatbot for clinic", description="RAG bot",
          skills=["Python"], payment_type="fixed", budget_usd=800, client_id="c1")
PREFS = {"behaviour": "genuine", "must_have_skills": ["LangChain", "FastAPI"],
         "budget_ceiling": {"type": "fixed", "usd": 900}, "dislikes_generic_opening": True,
         "reply_propensity": 0.6}
TAILORED = ("Your customer support chatbot for the clinic is close to one I shipped with "
            "LangChain and FastAPI.")
GENERIC = "Hello, I am a highly skilled expert and can do this job with 100% satisfaction."
GOOD = {"hired", "interview", "replied"}


def proposal(number: int, letter: str) -> dict:
    return {"proposal_id": f"p{number}", "cover_letter": letter, "bid_type": "fixed",
            "bid_amount_usd": 700}


def test_tailored_letters_beat_generic_ones(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    tailored = [decide_outcome(settings, PREFS, JOB, proposal(n, TAILORED)) for n in range(40)]
    generic = [decide_outcome(settings, PREFS, JOB, proposal(n, GENERIC)) for n in range(40)]
    assert sum(o in GOOD for o in tailored) > sum(o in GOOD for o in generic) + 10
    assert tailored == [decide_outcome(settings, PREFS, JOB, proposal(n, TAILORED))
                        for n in range(40)]  # seeded


def test_scammers_always_scam(tmp_path: Path) -> None:
    outcome = decide_outcome(make_settings(tmp_path), {"behaviour": "scammer"}, JOB,
                             proposal(1, TAILORED))
    assert outcome == "scam"


def test_llm_mode_falls_back_to_rules_when_unreachable(tmp_path: Path) -> None:
    rules = make_settings(tmp_path)
    sim_config = rules.config.client_sim.model_copy(update={"mode": "llm"})
    llm = rules.model_copy(update={
        "config": rules.config.model_copy(update={"client_sim": sim_config}),
        "llm_base_url": "http://127.0.0.1:9", "llm_model": "test", "llm_prompt": "{proposal}",
    })
    letter = proposal(3, TAILORED)
    assert decide_outcome(llm, PREFS, JOB, letter) == decide_outcome(rules, PREFS, JOB, letter)


class FakeReply:
    def __init__(self, content: object) -> None:
        self._content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"choices": [{"message": {"content": self._content}}]}


def llm_settings(tmp_path: Path):
    rules = make_settings(tmp_path)
    sim_config = rules.config.client_sim.model_copy(update={"mode": "llm"})
    return rules.model_copy(update={
        "config": rules.config.model_copy(update={"client_sim": sim_config}),
        "llm_base_url": "http://llm.test", "llm_model": "test", "llm_prompt": "{proposal}",
    })


def test_llm_mode_uses_the_model_answer(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeReply('{"outcome": "interview"}'))
    assert decide_outcome(llm_settings(tmp_path), PREFS, JOB, proposal(4, GENERIC)) == "interview"


def test_llm_mode_survives_malformed_replies(tmp_path: Path, monkeypatch) -> None:
    rules = make_settings(tmp_path)
    expected = decide_outcome(rules, PREFS, JOB, proposal(5, GENERIC))
    for content in [None, "[1, 2]", '{"outcome": "maybe"}']:
        monkeypatch.setattr(httpx, "post", lambda *a, c=content, **k: FakeReply(c))
        assert decide_outcome(llm_settings(tmp_path), PREFS, JOB, proposal(5, GENERIC)) == expected
