"""Regenerating a paragraph keeps the policy's required disclosure line."""

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from agent.nodes.writer import rewrite_paragraph

JOB = {"job_id": "j1", "title": "Prompts", "description": "Write prompts."}
EVIDENCE = {"ai-cs-01": {"id": "ai-cs-01", "type": "case_study", "title": "Prompt suite",
                         "text": "Built a prompt regression suite."}}
DISCLOSURE = "This proposal was AI-assisted and reviewed by me."


async def test_the_disclosure_survives_a_rewrite() -> None:
    model = FakeListChatModel(responses=["I built a prompt regression suite [ai-cs-01]."])
    paragraph = f"Happy to talk on a call.\n{DISCLOSURE}"
    rewritten = await rewrite_paragraph(JOB, EVIDENCE, paragraph, model)
    assert rewritten.endswith(DISCLOSURE) and "ai-cs-01" in rewritten


async def test_a_disclosure_only_paragraph_is_left_alone() -> None:
    model = FakeListChatModel(responses=["unused"])
    assert await rewrite_paragraph(JOB, EVIDENCE, DISCLOSURE, model) == DISCLOSURE
