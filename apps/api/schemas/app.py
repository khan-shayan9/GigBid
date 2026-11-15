"""Request and response models for sign-in, onboarding, settings, inbox, messages and analytics."""

from typing import Literal

from pydantic import BaseModel, Field

from apps.api.schemas.runs import RunSummary
from mcp_servers.marketplace.schemas import Job, Message, Proposal

Autonomy = Literal["manual", "auto_skip_low_fit"]  # never auto-send (spec §2)


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=200)


class Profile(BaseModel):
    """One account's onboarding answers and settings."""

    account: str
    persona: str | None = Field(None, description="the GigSim user and portfolio this account uses")
    hourly_floor_usd: float = Field(30, ge=0, le=1000)
    weekly_connects_budget: int = Field(60, ge=0, le=1000)
    saved_searches: list[str] = Field(default=[], max_length=10)
    autonomy: Autonomy = "manual"


class ProfileIn(BaseModel):
    persona: str | None = None
    hourly_floor_usd: float = Field(30, ge=0, le=1000)
    weekly_connects_budget: int = Field(60, ge=0, le=1000)
    saved_searches: list[str] = Field(default=[], max_length=10)
    autonomy: Autonomy = "manual"


class Session(BaseModel):
    account: str
    profile: Profile
    personas: list[str]
    marketplace_mode: str
    policy_version: str


class Connections(BaseModel):
    marketplace_mode: str
    marketplace: bool
    connects_balance: int | None = None
    upwork_connected: bool


class UploadOut(BaseModel):
    saved_as: str
    bytes: int


class InboxItem(BaseModel):
    job: Job
    run: RunSummary | None = None


class Inbox(BaseModel):
    items: list[InboxItem]


class MessageThread(BaseModel):
    thread_id: str
    job_id: str
    messages: list[Message]
    latest_client_message_id: str | None = None
    reply_run: RunSummary | None = None


class MessageThreads(BaseModel):
    threads: list[MessageThread]


PipelineStage = Literal["awaiting_approval", "drafted", "submitted", "viewed", "replied",
                        "interview", "hired", "lost"]


class PipelineCard(BaseModel):
    stage: PipelineStage
    job_id: str
    title: str
    thread_id: str | None = None
    proposal: Proposal | None = None


class Pipeline(BaseModel):
    cards: list[PipelineCard]


class RateRow(BaseModel):
    category: str
    submitted: int
    replied: int
    hired: int


class ReasonCount(BaseModel):
    reason: str
    count: int


class Analytics(BaseModel):
    jobs_analysed: int
    decisions: dict[str, int]
    approvals: dict[str, int]
    needs_attention: int
    rates_by_category: list[RateRow]
    connects_spent: int
    outcomes: dict[str, int]
    top_rejection_reasons: list[ReasonCount]
    cost_and_latency: str = Field(description="why cost and latency are not shown yet")


class MemoryItem(BaseModel):
    id: str
    kind: Literal["style", "outcome"]
    summary: str


class MemoryList(BaseModel):
    items: list[MemoryItem]
