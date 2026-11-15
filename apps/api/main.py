"""The GigBid web API. `create_app(**overrides)` lets tests inject the MCP and model factories."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from apps.api.errors import install_error_handlers
from apps.api.routers import (
    analytics,
    approvals,
    auth,
    jobs,
    messages,
    profile,
    proposals,
    runs,
)
from apps.api.runtime import open_runtime


def create_app(**runtime_overrides: Any) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with open_runtime(**runtime_overrides) as runtime:
            app.state.runtime = runtime
            yield

    app = FastAPI(title="GigBid API", version="0.6.0", lifespan=lifespan)
    install_error_handlers(app)
    for module in (auth, profile, jobs, runs, approvals, proposals, messages, analytics):
        app.include_router(module.router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "gigbid-api"}

    return app


app = create_app()  # env comes from the process (compose env_file, or `make api`)
