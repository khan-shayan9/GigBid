"""Critic: check grounding, personalisation and length; send the draft back with reasons.

shortcut: rule checks only (citations present, no generic opening, word limit); an LLM critic
on the strong model (agent/prompts/critic.md) replaces this when the token budget allows.
"""

import re

from agent.handoffs import Critique, ProposalDraft
from agent.nodes.writer import MAX_WORDS
from agent.state import GigBidState

GENERIC_OPENING = re.compile(r"^\s*(hi|hello|dear)?[\s,]*(i am|i'm) an? (experienced|expert)",
                             re.IGNORECASE)


def critique(draft: ProposalDraft) -> Critique:
    reasons = []
    if not draft.evidence_ids:
        reasons.append("No claim cites portfolio evidence; cite at least one evidence id.")
    if GENERIC_OPENING.search(draft.cover_letter):
        reasons.append("Open with the client's problem, not a generic self-introduction.")
    if len(draft.cover_letter.split()) > MAX_WORDS:
        reasons.append(f"Cut the letter to at most {MAX_WORDS} words.")
    return Critique(passed=not reasons, reasons=reasons)


async def critic(state: GigBidState) -> GigBidState:
    verdict = critique(ProposalDraft(**state["proposal_draft"]))
    return {"critique": verdict.model_dump(), "revisions": state.get("revisions", 0)
            + (0 if verdict.passed else 1)}
