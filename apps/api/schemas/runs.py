"""Request and response models for graph runs, approvals and the run viewer."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from agent.handoffs import (
    BidDecision,
    ComplianceVerdict,
    Critique,
    FitReport,
    JobSpec,
    PriceQuote,
    ProposalDraft,
    RiskReport,
)
from mcp_servers.marketplace.schemas import Job, Proposal, SubmitResult
from rag.verify import ClaimVerdict

RunKind = Literal["bid", "conversation"]


class RunRef(BaseModel):
    thread_id: str


class EvidenceItem(BaseModel):
    id: str
    type: str
    title: str
    text: str
    score: float | None = None


class Slot(BaseModel):
    start: str
    end: str


class TimelineStep(BaseModel):
    step: int
    nodes: list[str]
    at: datetime | None = None


class Preview(BaseModel):
    """The marketplace's dry run: what will be sent and what it costs. Nothing was spent."""

    proposal: Proposal | None = None
    unavailable: str | None = None


class RunDetail(BaseModel):
    thread_id: str
    kind: RunKind
    running: bool
    pending_approval: bool
    status: str | None = Field(None, description="dead_letter or needs_attention when stopped")
    errors: list[str] = []
    steps: int = 0
    tokens_used: int = 0
    timeline: list[TimelineStep] = []
    approval_status: str | None = None
    # bid runs
    job: Job | None = None
    job_spec: JobSpec | None = None
    risk_report: RiskReport | None = None
    fit_report: FitReport | None = None
    decision: BidDecision | None = None
    price_quote: PriceQuote | None = None
    draft: ProposalDraft | None = None
    evidence: list[EvidenceItem] = []
    claims: list[ClaimVerdict] = []
    critique: Critique | None = None
    compliance: ComplianceVerdict | None = None
    revisions: int = 0
    preview: Preview | None = None
    submission: SubmitResult | None = None
    # conversation runs
    client_message: str | None = None
    intent: str | None = None
    reply: str | None = None
    slots: list[Slot] = []
    sent: dict[str, Any] | None = None


class RunSummary(BaseModel):
    thread_id: str
    kind: RunKind
    subject: str = Field(description="job id or client message id")
    title: str
    category: str | None = Field(None, description="the job's first listed skill")
    running: bool
    pending_approval: bool
    status: str | None = None
    approval_status: str | None = None
    decision: str | None = None
    fit_score: float | None = None
    risk_score: float | None = None
    risk_flags: list[str] = []
    price: PriceQuote | None = None
    updated_at: datetime | None = None


class RunList(BaseModel):
    runs: list[RunSummary]


class ResumeIn(BaseModel):
    action: Literal["approve", "edit", "reject"]
    cover_letter: str | None = Field(None, min_length=1, max_length=5000)
    reply: str | None = Field(None, min_length=1, max_length=3000)
    reason: str | None = Field(None, max_length=500)


class RegenerateIn(BaseModel):
    paragraph: str = Field(min_length=1, max_length=3000)


class RegenerateOut(BaseModel):
    paragraph: str
