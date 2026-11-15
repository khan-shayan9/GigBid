"""Verifier: grade every claim in the draft against its evidence; drop unsupported sentences.

Runs between the Writer and the Critic (wired into the bid graph in Phase 5). The grading logic
is `rag/verify.py`; this node supplies the model and the prompt.
"""

import asyncio
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig

from agent.config import load_prompt
from agent.handoffs import ProposalDraft
from agent.state import GigBidState
from rag.verify import ClaimVerdict, remove_unsupported, verify_claims

NODE = "verifier"


async def verify_draft(draft: ProposalDraft, evidence: list[dict[str, Any]],
                       model: BaseChatModel) -> tuple[ProposalDraft, list[ClaimVerdict]]:
    """The draft without unsupported claims, and the verdicts on the original draft."""
    def complete(prompt: str) -> str:
        return str(model.invoke(prompt).content)

    verdicts = await asyncio.to_thread(verify_claims, draft.cover_letter, evidence, complete,
                                       load_prompt(NODE))
    letter = remove_unsupported(draft.cover_letter, verdicts)
    cited = [id_ for id_ in draft.evidence_ids if f"[{id_}]" in letter]
    return draft.model_copy(update={"cover_letter": letter, "evidence_ids": cited}), verdicts


async def verifier(state: GigBidState, config: RunnableConfig) -> GigBidState:
    """Graph node. `config["configurable"]` carries the run's `model`."""
    draft = ProposalDraft(**state["proposal_draft"])
    cleaned, verdicts = await verify_draft(draft, state.get("evidence", []),
                                           config["configurable"]["model"])
    return {"proposal_draft": cleaned.model_dump(),
            "claim_verification": [verdict.model_dump() for verdict in verdicts]}
