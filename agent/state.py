import operator
from typing import Annotated, Any, TypedDict


class GigBidState(TypedDict, total=False):
    """What one job's thread needs now. Traces and long-term memory live elsewhere (C2)."""

    job: dict[str, Any]
    job_spec: dict[str, Any]
    risk_report: dict[str, Any]
    fit_report: dict[str, Any]
    decision: dict[str, Any]
    evidence: list[dict[str, Any]]
    price_quote: dict[str, Any]
    proposal_draft: dict[str, Any]
    claim_verification: list[dict[str, Any]]
    critique: dict[str, Any]
    revisions: int
    compliance_verdict: dict[str, Any]
    approval_status: str
    submission: dict[str, Any]
    # Parallel branches may each add errors; the reducer appends instead of overwriting.
    errors: Annotated[list[str], operator.add]
    # C4/C7 (agent/graphs/guard.py): counted per node; `status` is dead_letter or needs_attention.
    steps: Annotated[int, operator.add]
    tokens_used: Annotated[int, operator.add]
    # Two parallel nodes may both fail in one step; keep the latest status instead of erroring.
    status: Annotated[str, lambda old, new: new or old]


class ConversationState(TypedDict, total=False):
    """One client conversation thread."""

    thread_id: str
    message: str  # the client's latest message (untrusted)
    intent: str
    slots: list[dict[str, Any]]
    reply: str
    compliance_verdict: dict[str, Any]
    approval_status: str
    sent: dict[str, Any]
    errors: Annotated[list[str], operator.add]
