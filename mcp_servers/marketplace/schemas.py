"""Declared output schemas of the Marketplace MCP tools.

They mirror GigSim's public responses on purpose instead of importing `gigsim` (a separate,
frozen service). Unknown fields from the marketplace are dropped, so only these reach agents.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Money = Field(gt=0, le=1_000_000)


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
    connects_cost: int | None = None
    client_id: str
    posted_at: datetime


class JobPage(BaseModel):
    jobs: list[Job]
    total: int


class ClientContract(BaseModel):
    title: str
    paid_usd: float | None = None
    rating: float | None = None


class ClientHistory(BaseModel):
    client_id: str
    country: str | None = None
    payment_verified: bool = False
    enterprise: bool = False
    total_spent_usd: float | None = None
    rating: float | None = None
    feedback_count: int | None = None
    history: list[ClientContract] = []


class ConnectsBalance(BaseModel):
    user_id: str
    balance: int


class MarketRates(BaseModel):
    domains: dict[str, dict[str, Any]]


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


class Bid(BaseModel):
    type: Literal["fixed", "hourly"]
    amount_usd: float = Money


class Proposal(BaseModel):
    proposal_id: str
    job_id: str
    status: str
    cover_letter: str
    bid: Bid
    screening_answers: list[str]
    connects_cost: int
    created_at: datetime
    dry_run: bool = Field(False, description="True: a preview; nothing was stored or sent")


class SubmitResult(BaseModel):
    proposal: Proposal
    connects_cost: int
    balance_after: int
    dry_run: bool = Field(False, description="True: a preview; no Connects were spent")
