"""GigSim FastAPI app. Run: uvicorn --factory gigsim.app:create_app --port 8081"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from gigsim import read_routes, write_routes
from gigsim.clock import SimClock
from gigsim.db import StateDB
from gigsim.guard import Guard
from gigsim.models import ClockAdvance, ClockState, Health
from gigsim.policy import load_policy
from gigsim.settings import Settings, load_settings
from gigsim.sim import AdminDep, Sim, SimDep
from gigsim.store import load_seed


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    seed = load_seed(settings.seed_dirs, settings.config.default_client_prefs)
    db = StateDB(settings.db_path)
    clock = SimClock(db, settings.config.time_scale, settings.epoch)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        db.close()

    app = FastAPI(title="GigSim", version="1.0.0", lifespan=lifespan)
    app.state.sim = Sim(
        settings=settings, db=db, clock=clock, seed=seed, guard=Guard(settings),
        policy=load_policy(settings.policy_path),
    )
    app.include_router(read_routes.router)
    app.include_router(write_routes.router)
    app.add_api_route("/health", health, methods=["GET"], response_model=Health)
    app.add_api_route(
        "/admin/clock/advance", advance_clock, methods=["POST"], response_model=ClockState
    )
    app.add_api_route("/admin/reset", reset_state, methods=["POST"], response_model=ClockState)
    app.add_exception_handler(Exception, internal_error)
    return app


def health() -> Health:
    return Health(status="ok", service="gigsim")


def advance_clock(body: ClockAdvance, _: AdminDep, sim: SimDep) -> ClockState:
    sim.clock.advance(body.minutes)
    return sim.clock_state()


def reset_state(_: AdminDep, sim: SimDep) -> ClockState:
    """Clear proposals, messages, ledger, idempotency keys, fault and rate state; clock to 0."""
    sim.db.reset()
    sim.clock.reset()
    sim.guard.reset()
    return sim.clock_state()


async def internal_error(request: Request, error: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": {"code": "internal_error", "message": "Internal simulator error."}},
    )
