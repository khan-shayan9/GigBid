"""Serve the real API with the fake marketplace for Playwright (apps/web/playwright.config.ts).

Adds two test-only routes, never present in the real app: POST /__test__/reset (fresh market and
runtime state) and POST /__test__/marketplace?down=true|false&slow=<seconds> (degraded mode, slow runs).
Sign in as `reviewer` / `e2e-password` (a test account made here).
"""

import os
import secrets
import sys

import uvicorn
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from apps.api.auth.users import hash_password
from apps.api.main import create_app
from apps.api.runtime import Runtime
from tests.e2e.fake_backend import FakeMarket, fake_overrides

E2E_PASSWORD = "e2e-password"


def build() -> object:
    os.environ.update({"APP_SECRET_KEY": secrets.token_hex(16), "API_PERSISTENCE": "memory",
                       "APP_USERS": f"reviewer={hash_password(E2E_PASSWORD)}"})
    market = FakeMarket()
    overrides = fake_overrides(market)
    app = create_app(**overrides)

    @app.post("/__test__/reset", include_in_schema=False)
    async def reset() -> dict[str, bool]:
        market.reset()
        app.state.runtime = Runtime(MemorySaver(), InMemoryStore(), **overrides)
        return {"ok": True}

    @app.post("/__test__/marketplace", include_in_schema=False)
    async def marketplace(down: bool, slow: float = 0.0) -> dict[str, float]:
        market.down, market.slow = down, slow
        return {"down": down, "slow": slow}

    return app


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8010
    uvicorn.run(build(), host="127.0.0.1", port=port, log_level="warning")
