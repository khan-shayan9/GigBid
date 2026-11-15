"""B3: claims are graded against evidence and unsupported sentences leave the draft."""

import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from agent.handoffs import ProposalDraft
from agent.nodes.verifier import verify_draft
from rag.verify import (
    VerificationFailed,
    count_labels,
    remove_unsupported,
    split_sentences,
    verify_claims,
)

DRAFT = ("Your clinic needs fewer calls. I built a leaflet bot for a clinic [ai-cs-01]. "
         "It cut calls by 90% [ai-cs-01].\n\nI have ten years of Rust. Happy to talk.")
EVIDENCE = [{"id": "ai-cs-01", "title": "MedAssist", "text": "Clinic leaflet bot; fewer calls."}]
REPLY = json.dumps([
    {"sentence": 1, "claim": "built a clinic leaflet bot", "label": "supported",
     "evidence_ids": ["ai-cs-01"]},
    {"sentence": 2, "claim": "cut calls by 90%", "label": "partly_supported"},
    {"sentence": 3, "claim": "ten years of Rust", "label": "unsupported"},
    {"sentence": 9, "claim": "out of range", "label": "unsupported"}])


def test_split_sentences_numbers_across_paragraphs() -> None:
    assert split_sentences(DRAFT)[3] == "I have ten years of Rust."


def test_verdicts_are_parsed_and_unsupported_sentences_removed() -> None:
    prompts: list[str] = []
    verdicts = verify_claims(DRAFT, EVIDENCE, lambda prompt: prompts.append(prompt) or
                             f"Here you go:\n{REPLY}", "{sentences}\n---\n{evidence}")
    assert "3. I have ten years of Rust." in prompts[0] and "[ai-cs-01] MedAssist" in prompts[0]
    assert count_labels(verdicts) == {"supported": 1, "partly_supported": 1, "unsupported": 1}
    assert remove_unsupported(DRAFT, verdicts) == (
        "Your clinic needs fewer calls. I built a leaflet bot for a clinic [ai-cs-01]. "
        "It cut calls by 90% [ai-cs-01].\n\nHappy to talk.")


def test_an_unusable_reply_raises() -> None:
    with pytest.raises(VerificationFailed):
        verify_claims(DRAFT, EVIDENCE, lambda _: "I think it is fine.", "{sentences}{evidence}")


async def test_the_node_drops_unsupported_claims_and_their_citations() -> None:
    draft = ProposalDraft(job_id="job-1", cover_letter="I built X [a]. I built Y [b].",
                          evidence_ids=["a", "b"])
    reply = json.dumps([{"sentence": 1, "claim": "built Y", "label": "unsupported"}])
    cleaned, verdicts = await verify_draft(draft, EVIDENCE, FakeListChatModel(responses=[reply]))
    assert cleaned.cover_letter == "I built X [a]." and cleaned.evidence_ids == ["a"]
    assert verdicts[0].label == "unsupported"
