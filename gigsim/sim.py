"""The running simulator's state and the FastAPI dependencies that hand it to routes."""

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from fastapi import Depends, Request

from gigsim.clock import SimClock
from gigsim.db import StateDB
from gigsim.guard import Guard
from gigsim.models import ClockState
from gigsim.policy import Policy
from gigsim.settings import Settings
from gigsim.store import Seed


@dataclass
class Sim:
    settings: Settings
    db: StateDB
    clock: SimClock
    seed: Seed
    guard: Guard
    policy: Policy

    def job_released(self, job_id: str, now: float) -> bool:
        release = self.seed.release_min.get(job_id)
        return release is not None and release <= now

    def client_visible(self, client_id: str, now: float) -> bool:
        # A client is visible once any of its jobs is released, so ids leak no future stream.
        first = self.seed.client_first_release.get(client_id)
        return first is not None and first <= now

    def clock_state(self) -> ClockState:
        minutes = self.clock.minutes()
        return ClockState(sim_minutes=minutes, sim_time=self.clock.at(minutes))

    def posted_at(self, job_id: str) -> datetime:
        return self.clock.at(self.seed.release_min[job_id])


def get_sim(request: Request) -> Sim:
    return request.app.state.sim


SimDep = Annotated[Sim, Depends(get_sim)]


def require_user(request: Request, sim: SimDep) -> str:
    return sim.guard.user(request)


def require_admin(request: Request, sim: SimDep) -> None:
    sim.guard.admin(request)


UserDep = Annotated[str, Depends(require_user)]
AdminDep = Annotated[None, Depends(require_admin)]
