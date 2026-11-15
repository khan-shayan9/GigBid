"""The single marketplace interface. GigSim and live Upwork adapters both implement it (R1).

One adapter instance serves one user, so no method takes a user id. Methods return plain JSON
dicts; the Marketplace MCP server validates them into its declared output schemas.
"""

from typing import Any, Protocol


class MarketplaceError(Exception):
    """The marketplace refused the call (4xx). `code` is the marketplace's stable error code."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.status, self.code, self.message = status, code, message


class MarketplaceUnavailable(Exception):
    """The marketplace did not answer after bounded retries (5xx, 429 or network). Degraded mode."""


class MarketplacePort(Protocol):
    async def search_jobs(
        self, query: str = "", skills: list[str] | None = None, payment_type: str | None = None,
        since: str | None = None, limit: int = 20, offset: int = 0,
    ) -> dict[str, Any]: ...

    async def get_job(self, job_id: str) -> dict[str, Any]: ...

    async def get_client_history(self, client_id: str) -> dict[str, Any]: ...

    async def get_connects_balance(self) -> dict[str, Any]: ...

    async def get_market_rates(self) -> dict[str, Any]: ...

    async def list_messages(
        self, thread_id: str | None = None, since: str | None = None, limit: int = 100,
    ) -> dict[str, Any]: ...

    # Writes take the caller's idempotency key: a retry with the same key never acts twice.
    async def create_proposal_draft(
        self, payload: dict[str, Any], idempotency_key: str, dry_run: bool,
    ) -> dict[str, Any]: ...

    async def submit_proposal(
        self, proposal_id: str, idempotency_key: str, dry_run: bool,
    ) -> dict[str, Any]: ...

    async def send_message(
        self, thread_id: str, text: str, idempotency_key: str, dry_run: bool,
    ) -> dict[str, Any]: ...
