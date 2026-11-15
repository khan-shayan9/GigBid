from typing import Literal

from pydantic import BaseModel, Field


class JobSpec(BaseModel):
    job_id: str
    title: str
    deliverables: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    budget_min: float | None = None
    budget_max: float | None = None

class RiskReport(BaseModel):
    score: float = Field(ge=0, le=1)
    flags: list[str] = Field(default_factory=list)
    explanation: str

class RequirementMatch(BaseModel):
    requirement: str
    evidence_ids: list[str] = Field(default_factory=list)
    best_score: float = 0.0
    covered: bool = False


class FitReport(BaseModel):
    score: float = Field(ge=0, le=1)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    matrix: list[RequirementMatch] = Field(default_factory=list)  # requirement -> its evidence

class ProposalDraft(BaseModel):
    job_id: str
    cover_letter: str
    screening_answers: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    status: str = "pending_review"


class BidDecision(BaseModel):
    decision: Literal["bid", "watch", "skip"]
    reasons: list[str] = Field(default_factory=list)


class PriceQuote(BaseModel):
    bid_type: Literal["fixed", "hourly"]
    amount_usd: float = Field(gt=0)
    rationale: str


class Critique(BaseModel):
    passed: bool
    reasons: list[str] = Field(default_factory=list)


class ComplianceVerdict(BaseModel):
    allowed: bool
    violations: list[str] = Field(default_factory=list)
