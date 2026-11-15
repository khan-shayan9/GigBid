"""Human approval and submission (C5): the only path to a real marketplace write.

`approval` pauses the thread with `interrupt()` and the full approval payload. The resume value
is {"action": "approve" | "edit" | "reject", "cover_letter"?: str, "reason"?: str}.
`submit` then creates and submits the proposal with idempotency keys derived from the thread,
so a resumed or replayed run cannot submit twice.
"""

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store
from langgraph.types import interrupt

from agent.config import load_policy
from agent.handoffs import ProposalDraft
from agent.memory.promotion_rules import promote_style_edit
from agent.nodes.compliance import check
from agent.state import GigBidState

NODE = "submitter"


async def approval(state: GigBidState, config: RunnableConfig) -> GigBidState:
    answer = interrupt({
        "draft": state["proposal_draft"], "evidence": state.get("evidence", []),
        "claims": state.get("claim_verification", []), "risk": state["risk_report"],
        "price": state["price_quote"], "critique": state.get("critique", {}),
        "compliance": state["compliance_verdict"]})
    if answer.get("action") == "reject":
        return {"approval_status": f"rejected: {answer.get('reason', '')}".strip()}
    draft = ProposalDraft(**state["proposal_draft"])
    if answer.get("action") == "edit":
        verdict = check(answer["cover_letter"], load_policy())  # an edit is re-checked
        if not verdict.allowed:
            return {"approval_status": "blocked_after_edit",
                    "compliance_verdict": verdict.model_dump()}
        store = get_store()  # long-term memory; None when the graph runs without a store
        if store is not None:  # an approved, compliance-clean edit is a style candidate (R7)
            await promote_style_edit(store, config["configurable"].get("user_id", "default"),
                                     draft.cover_letter, answer["cover_letter"],
                                     compliance_clean=True)
        draft = draft.model_copy(update={"cover_letter": answer["cover_letter"]})
    return {"approval_status": "approved", "proposal_draft": draft.model_dump()}


async def submit(state: GigBidState, config: RunnableConfig) -> GigBidState:
    options = config["configurable"]
    draft, price = state["proposal_draft"], state["price_quote"]
    key = f"{options['thread_id']}-{draft['job_id']}"
    created = await options["mcp"].call(NODE, "create_proposal_draft", {
        "job_id": draft["job_id"], "cover_letter": draft["cover_letter"],
        "bid_type": price["bid_type"], "bid_amount_usd": price["amount_usd"],
        "idempotency_key": f"draft-{key}", "dry_run": False})
    submitted = await options["mcp"].call(NODE, "submit_proposal", {
        "proposal_id": created["proposal_id"], "idempotency_key": f"submit-{key}",
        "dry_run": False})
    return {"submission": submitted}
