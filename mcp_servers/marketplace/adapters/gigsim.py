"""GigSim adapter for the marketplace port: HTTP only, never imports `gigsim`."""

import asyncio
from typing import Any

import httpx

from agent.marketplace_port import MarketplaceError, MarketplaceUnavailable

MAX_ATTEMPTS = 4
BACKOFF_BASE_S = 0.5  # 0.5, 1, 2 s between attempts
MAX_RETRY_AFTER_S = 10.0  # never park a tool call longer than this on one 429
REQUEST_TIMEOUT_S = 10.0


class GigSimAdapter:
    def __init__(self, base_url: str, token: str, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=REQUEST_TIMEOUT_S)
        self._headers = {"Authorization": f"Bearer {token}"}

    async def search_jobs(
        self, query: str = "", skills: list[str] | None = None, payment_type: str | None = None,
        since: str | None = None, limit: int = 20, offset: int = 0,
    ) -> dict[str, Any]:
        params = {"q": query, "skills": ",".join(skills or []), "payment_type": payment_type,
                  "since": since, "limit": limit, "offset": offset}
        return await self._call("GET", "/jobs", params=params)

    async def get_job(self, job_id: str) -> dict[str, Any]:
        return await self._call("GET", f"/jobs/{job_id}")

    async def get_client_history(self, client_id: str) -> dict[str, Any]:
        return await self._call("GET", f"/clients/{client_id}")

    async def get_connects_balance(self) -> dict[str, Any]:
        return await self._call("GET", "/connects")

    async def get_market_rates(self) -> dict[str, Any]:
        return await self._call("GET", "/market/rates")

    async def list_messages(
        self, thread_id: str | None = None, since: str | None = None, limit: int = 100,
    ) -> dict[str, Any]:
        params = {"thread_id": thread_id, "since": since, "limit": limit}
        return await self._call("GET", "/messages", params=params)

    async def list_proposals(self) -> dict[str, Any]:
        return await self._call("GET", "/proposals")

    async def create_proposal_draft(
        self, payload: dict[str, Any], idempotency_key: str, dry_run: bool,
    ) -> dict[str, Any]:
        return await self._call("POST", "/proposals", json=payload, key=idempotency_key,
                                params={"dry_run": dry_run})

    async def submit_proposal(
        self, proposal_id: str, idempotency_key: str, dry_run: bool,
    ) -> dict[str, Any]:
        return await self._call("POST", f"/proposals/{proposal_id}/submit", key=idempotency_key,
                                params={"dry_run": dry_run})

    async def send_message(
        self, thread_id: str, text: str, idempotency_key: str, dry_run: bool,
    ) -> dict[str, Any]:
        return await self._call("POST", "/messages", json={"thread_id": thread_id, "text": text},
                                key=idempotency_key, params={"dry_run": dry_run})

    async def _call(
        self, method: str, path: str, params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None, key: str | None = None,
    ) -> dict[str, Any]:
        headers = self._headers | ({"Idempotency-Key": key} if key else {})
        query = {name: value for name, value in (params or {}).items() if value not in (None, "")}
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = await self._client.request(method, path, params=query, json=json,
                                                      headers=headers)
            except httpx.TransportError:
                response = None
            if response is not None and response.status_code < 400:
                return response.json()
            if response is not None and response.status_code < 500 and response.status_code != 429:
                raise _refusal(response)
            if attempt + 1 < MAX_ATTEMPTS:
                # Writes are safe to retry: the same Idempotency-Key replays a committed write.
                await asyncio.sleep(_wait_s(response, attempt))
        raise MarketplaceUnavailable(f"GigSim did not answer {method} {path} after {MAX_ATTEMPTS} tries")


def _wait_s(response: httpx.Response | None, attempt: int) -> float:
    if response is not None and response.status_code == 429:
        # GigSim returns Retry-After on 429; honour it so we stay under the per-user limit.
        return min(float(response.headers.get("Retry-After", 1)), MAX_RETRY_AFTER_S)
    return BACKOFF_BASE_S * 2**attempt


def _refusal(response: httpx.Response) -> MarketplaceError:
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, dict) and "code" in detail:
        message = str(detail.get("message", ""))
        if detail.get("violations"):  # policy_violation: the agent needs the rules to fix the draft
            message += f" Violations: {detail['violations']}"
        return MarketplaceError(response.status_code, detail["code"], message)
    return MarketplaceError(response.status_code, "invalid_request", str(detail or response.text))
