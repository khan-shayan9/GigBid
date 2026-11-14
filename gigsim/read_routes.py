"""Read endpoints: jobs, clients, Connects balance and market statistics."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from gigsim.guard import api_error
from gigsim.models import (
    Client,
    ClockState,
    ConnectsBalance,
    HistoricalPage,
    Job,
    JobOut,
    JobPage,
    MarketRates,
)
from gigsim.sim import Sim, SimDep, UserDep

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

Limit = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
Offset = Annotated[int, Query(ge=0)]

router = APIRouter()


@router.get("/jobs", response_model=JobPage)
def search_jobs(
    user_id: UserDep,
    sim: SimDep,
    q: Annotated[str, Query(max_length=200, description="All words must appear")] = "",
    skills: Annotated[str, Query(max_length=500, description="Comma list; any may match")] = "",
    payment_type: Literal["fixed", "hourly"] | None = None,
    since: Annotated[datetime | None, Query(description="Only jobs posted after this")] = None,
    limit: Limit = DEFAULT_PAGE_SIZE,
    offset: Offset = 0,
) -> JobPage:
    terms = q.lower().split()
    wanted_skills = {skill.strip().lower() for skill in skills.split(",") if skill.strip()}
    since_utc = since if since is None or since.tzinfo else since.replace(tzinfo=UTC)
    now = sim.clock.minutes()
    matches = []
    for job in sim.seed.jobs.values():
        if not sim.job_released(job.job_id, now):
            continue
        if since_utc and sim.posted_at(job.job_id) <= since_utc:
            continue
        if payment_type and job.payment_type != payment_type:
            continue
        if wanted_skills and not wanted_skills & {skill.lower() for skill in job.skills}:
            continue
        text = " ".join([job.title, job.description, *job.skills]).lower()
        if all(term in text for term in terms):
            matches.append(job)
    matches.sort(key=lambda job: (-sim.seed.release_min[job.job_id], job.job_id))
    page = matches[offset : offset + limit]
    return JobPage(jobs=[_job_out(sim, job) for job in page], total=len(matches))


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, user_id: UserDep, sim: SimDep) -> JobOut:
    job = sim.seed.jobs.get(job_id)
    if job is None or not sim.job_released(job_id, sim.clock.minutes()):
        raise api_error(404, "job_not_found", f"No job {job_id}.")
    return _job_out(sim, job)


@router.get("/clients/{client_id}", response_model=Client)
def get_client(client_id: str, user_id: UserDep, sim: SimDep) -> Client:
    client = sim.seed.clients.get(client_id)
    if client is None or not sim.client_visible(client_id, sim.clock.minutes()):
        raise api_error(404, "client_not_found", f"No client {client_id}.")
    return client


@router.get("/time", response_model=ClockState)
def get_sim_time(user_id: UserDep, sim: SimDep) -> ClockState:
    """Current simulated time; posted_at and `since` use this clock, not wall time."""
    return sim.clock_state()


@router.get("/connects", response_model=ConnectsBalance)
def get_connects_balance(user_id: UserDep, sim: SimDep) -> ConnectsBalance:
    starting = sim.settings.config.users[user_id].starting_connects
    return ConnectsBalance(user_id=user_id, balance=starting + sim.db.connects_delta(user_id))


@router.get("/market/rates", response_model=MarketRates)
def get_market_rates(user_id: UserDep, sim: SimDep) -> MarketRates:
    return MarketRates(domains=sim.seed.market_domains)


@router.get("/market/historical", response_model=HistoricalPage)
def list_historical_jobs(
    user_id: UserDep,
    sim: SimDep,
    category: Annotated[str | None, Query(max_length=50)] = None,
    limit: Limit = DEFAULT_PAGE_SIZE,
    offset: Offset = 0,
) -> HistoricalPage:
    jobs = [
        job for job in sim.seed.historical_jobs.values()
        if category is None or job.category == category
    ]
    return HistoricalPage(jobs=jobs[offset : offset + limit], total=len(jobs))


def _job_out(sim: Sim, job: Job) -> JobOut:
    fields = job.model_dump() | {"connects_cost": sim.policy.connects_cost(job)}
    return JobOut(**fields, posted_at=sim.posted_at(job.job_id))
