"""Seed and response models. Fields are whitelisted: anything not declared here (source,
derived_from, history_source, hidden client preferences) is dropped on load and never served."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class HourlyRange(BaseModel):
    min: float | None = None
    max: float | None = None


class Job(BaseModel):
    job_id: str
    title: str
    description: str
    skills: list[str] = []
    experience_level: str | None = None
    payment_type: Literal["fixed", "hourly"]
    budget_usd: float | None = None
    hourly_usd: HourlyRange | None = None
    duration: str | None = None
    applicants: str | None = None
    connects_cost: int | None = Field(None, ge=0, description="None: the policy sets the cost")
    client_id: str


class JobOut(Job):
    posted_at: datetime


class JobPage(BaseModel):
    jobs: list[JobOut]
    total: int


class ClientContract(BaseModel):
    title: str
    paid_usd: float | None = None
    rating: float | None = None


class Client(BaseModel):
    client_id: str
    country: str | None = None
    payment_verified: bool = False
    enterprise: bool = False
    total_spent_usd: float | None = None
    rating: float | None = None
    feedback_count: int | None = None
    history: list[ClientContract] = []


class HistoricalJob(BaseModel):
    job_id: str
    category: str
    title: str
    description: str = ""
    payment_type: Literal["fixed", "hourly"]
    budget_usd: float | None = None
    hourly_usd: HourlyRange | None = None
    country: str | None = None
    posted_at: datetime


class HistoricalPage(BaseModel):
    jobs: list[HistoricalJob]
    total: int


class MarketRates(BaseModel):
    domains: dict[str, dict[str, Any]]


class ConnectsBalance(BaseModel):
    user_id: str
    balance: int


class ClockAdvance(BaseModel):
    minutes: float = Field(gt=0, le=60 * 24 * 365)


class ClockState(BaseModel):
    sim_minutes: float
    sim_time: datetime


class Health(BaseModel):
    status: str
    service: str


class Bid(BaseModel):
    type: Literal["fixed", "hourly"]
    amount_usd: float = Field(gt=0, le=1_000_000)


class ProposalIn(BaseModel):
    job_id: str = Field(min_length=1, max_length=100)
    cover_letter: str = Field(min_length=1, max_length=20_000)
    bid: Bid
    screening_answers: list[str] = Field(default=[], max_length=20)


class ProposalOut(BaseModel):
    proposal_id: str
    job_id: str
    status: str
    cover_letter: str
    bid: Bid
    screening_answers: list[str]
    connects_cost: int
    created_at: datetime
    dry_run: bool = False


class ProposalList(BaseModel):
    proposals: list[ProposalOut]


class SubmitResult(BaseModel):
    proposal: ProposalOut
    connects_cost: int
    balance_after: int
    dry_run: bool = False


class ProposalEvent(BaseModel):
    type: str
    at: datetime


class EventList(BaseModel):
    events: list[ProposalEvent]


class MessageIn(BaseModel):
    thread_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=10_000)


class Message(BaseModel):
    message_id: str
    thread_id: str
    job_id: str
    client_id: str
    sender: Literal["client", "freelancer"]
    text: str
    sent_at: datetime
    dry_run: bool = False


class MessageList(BaseModel):
    messages: list[Message]


class SeedMessage(BaseModel):
    message_id: str
    text: str
    sent_after_min: float = Field(ge=0)


class Conversation(BaseModel):
    conversation_id: str
    persona_id: str
    job_id: str
    client_id: str
    messages: list[SeedMessage]


class BudgetCeiling(BaseModel):
    type: Literal["fixed", "hourly"] | None = None
    usd: float | None = Field(None, ge=0)


class ClientPrefs(BaseModel):
    """Hidden client preferences: read by the client simulation, never served."""

    behaviour: Literal["genuine", "scammer"] = "genuine"
    must_have_skills: list[str] = []
    budget_ceiling: BudgetCeiling | None = None
    dislikes_generic_opening: bool = False
    reply_propensity: float = Field(0.5, ge=0, le=1)
