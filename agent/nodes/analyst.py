"""Job Analyst: turn a job post into a structured JobSpec.

shortcut: built from the post's structured fields (title, listed skills, budget) with no model
call; an LLM extraction of deliverables and hidden needs (agent/prompts/analyst.md) replaces it
when the token budget allows.
"""

from typing import Any

from agent.handoffs import JobSpec
from agent.state import GigBidState


def extract_job_spec(job: dict[str, Any]) -> JobSpec:
    hourly = job.get("hourly_usd") or {}
    budget = job.get("budget_usd")
    return JobSpec(job_id=job["job_id"], title=job["title"],
                   required_skills=list(job.get("skills", [])),
                   budget_min=hourly.get("min") if hourly else budget,
                   budget_max=hourly.get("max") if hourly else budget)


async def analyst(state: GigBidState) -> GigBidState:
    return {"job_spec": extract_job_spec(state["job"]).model_dump()}
