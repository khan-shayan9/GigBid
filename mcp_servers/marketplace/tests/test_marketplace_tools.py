"""Marketplace MCP tools through an in-memory MCP client, backed by an in-process GigSim."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from mcp import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session
from starlette.testclient import TestClient

from gigsim.app import create_app
from gigsim.settings import RateLimit
from mcp_servers.marketplace.adapters import gigsim as gigsim_adapter
from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter
from mcp_servers.marketplace.server import ServerSettings, create_server
from tests.integration.test_gigsim_reads import ADMIN, ALL_RELEASED_MIN, TOKEN, make_settings

LETTER = "Your clinic chatbot is close to the leaflet assistant I shipped with LangChain."


async def no_sleep(seconds: float) -> None:
    SLEEPS.append(seconds)


SLEEPS: list[float] = []


async def gigsim_client(tmp_path: Path, **config: Any) -> httpx.AsyncClient:
    settings = make_settings(tmp_path, faults=config.pop("faults", False))
    settings = settings.model_copy(update={"config": settings.config.model_copy(update=config)})
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(settings)),
                               base_url="http://gigsim")
    response = await client.post("/admin/clock/advance", json={"minutes": ALL_RELEASED_MIN},
                                 headers=ADMIN)
    assert response.status_code == 200
    return client


@asynccontextmanager
async def open_session(tmp_path: Path, http: httpx.AsyncClient | None = None,
                       rate_per_minute: int = 1000) -> AsyncIterator[ClientSession]:
    adapter = GigSimAdapter("http://gigsim", TOKEN, client=http or await gigsim_client(tmp_path))
    settings = ServerSettings(audit_path=tmp_path / "audit.jsonl", stdio_user="ai_ml_engineer",
                              rate_per_minute=rate_per_minute)
    server = create_server(settings, port_for=lambda user: adapter)
    async with create_connected_server_and_client_session(server) as session:
        yield session


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    SLEEPS.clear()
    monkeypatch.setattr(gigsim_adapter.asyncio, "sleep", no_sleep)


async def call(session: ClientSession, tool: str, **args: Any) -> dict[str, Any]:
    result = await session.call_tool(tool, args)
    assert not result.isError, result.content
    return result.structuredContent


async def error_of(session: ClientSession, tool: str, **args: Any) -> str:
    result = await session.call_tool(tool, args)
    assert result.isError
    return result.content[0].text.removeprefix(f"Error executing tool {tool}: ")


async def first_job(session: ClientSession) -> dict[str, Any]:
    return (await call(session, "search_jobs", limit=1))["jobs"][0]


async def test_reads_return_declared_fields_only(tmp_path: Path) -> None:
    async with open_session(tmp_path) as session:
        await _test_reads_return_declared_fields_only(session)


async def _test_reads_return_declared_fields_only(session: ClientSession) -> None:
    job = await first_job(session)
    assert job["connects_cost"] >= 1 and "source" not in job
    assert (await call(session, "get_job", job_id=job["job_id"]))["title"] == job["title"]
    client = await call(session, "get_client_history", client_id=job["client_id"])
    assert "behaviour" not in client and "history_source" not in client
    assert (await call(session, "get_connects_balance"))["balance"] == 120
    assert (await call(session, "get_market_rates"))["domains"]
    assert "messages" in await call(session, "list_messages", limit=5)


async def test_write_flow_previews_then_spends_once(tmp_path: Path) -> None:
    async with open_session(tmp_path) as session:
        await _test_write_flow_previews_then_spends_once(session)


async def _test_write_flow_previews_then_spends_once(session: ClientSession) -> None:
    job = await first_job(session)
    draft_args = {"job_id": job["job_id"], "cover_letter": LETTER, "bid_type": "fixed",
                  "bid_amount_usd": 500, "idempotency_key": "draft-0001"}
    preview = await call(session, "create_proposal_draft", **draft_args)  # dry_run by default
    assert preview["dry_run"] and preview["connects_cost"] == job["connects_cost"]
    draft = await call(session, "create_proposal_draft", **draft_args, dry_run=False)
    again = await call(session, "create_proposal_draft", **draft_args, dry_run=False)
    assert draft["proposal_id"] == again["proposal_id"] and not draft["dry_run"]

    submit_args = {"proposal_id": draft["proposal_id"], "idempotency_key": "submit-0001"}
    quote = await call(session, "submit_proposal", **submit_args)
    assert quote["dry_run"] and quote["balance_after"] == 120 - job["connects_cost"]
    assert (await call(session, "get_connects_balance"))["balance"] == 120
    for _ in range(2):  # a retried submit with the same key spends once
        await call(session, "submit_proposal", **submit_args, dry_run=False)
    assert (await call(session, "get_connects_balance"))["balance"] == 120 - job["connects_cost"]

    message_args = {"thread_id": draft["proposal_id"], "text": "Happy to start Monday.",
                    "idempotency_key": "message-0002"}
    assert (await call(session, "send_message", **message_args))["dry_run"]
    for _ in range(2):
        await call(session, "send_message", **message_args, dry_run=False)
    thread = await call(session, "list_messages", thread_id=draft["proposal_id"])
    assert [m["text"] for m in thread["messages"] if m["sender"] == "freelancer"] == [
        message_args["text"]]


async def test_marketplace_refusals_come_back_as_tool_errors(tmp_path: Path) -> None:
    async with open_session(tmp_path) as session:
        await _test_marketplace_refusals_come_back_as_tool_errors(session)


async def _test_marketplace_refusals_come_back_as_tool_errors(session: ClientSession) -> None:
    job = await first_job(session)
    message = await error_of(session, "create_proposal_draft", job_id=job["job_id"],
                             cover_letter=LETTER + " Mail me at jo@example.com.", bid_type="fixed",
                             bid_amount_usd=500, idempotency_key="draft-0002")
    assert message.startswith("policy_violation") and "no_email" in message
    assert "not_found" in await error_of(session, "get_job", job_id="no-such-job")
    assert "idempotency_key" in await error_of(  # input schema constraint: key too short
        session, "submit_proposal", proposal_id="p1", idempotency_key="short")


async def test_audit_log_masks_arguments(tmp_path: Path) -> None:
    async with open_session(tmp_path) as session:
        await _audit_calls(session)
    check_audit(tmp_path)


async def _audit_calls(session: ClientSession) -> None:
    await error_of(session, "send_message", thread_id="no-thread", text="call +1 555 123 4567",
                   idempotency_key="message-0001")
    await call(session, "get_connects_balance")


def check_audit(tmp_path: Path) -> None:
    lines = [json.loads(line) for line in (tmp_path / "audit.jsonl").read_text().splitlines()]
    assert [line["tool"] for line in lines] == ["send_message", "get_connects_balance"]
    assert lines[0]["arguments"]["text"] == "call [PHONE]"
    assert lines[0]["result"] == {"error": "thread_not_found"} and lines[0]["trace_id"]
    assert lines[1]["user"] == "ai_ml_engineer" and lines[1]["result"]["balance"] == 120


async def test_seeded_5xx_are_retried(tmp_path: Path) -> None:
    http = await gigsim_client(tmp_path, faults=True, fault_rate=0.5)
    async with open_session(tmp_path, http) as session:
        for job in (await call(session, "search_jobs", limit=10))["jobs"]:
            await call(session, "get_job", job_id=job["job_id"])
    assert SLEEPS  # some calls hit a seeded 503 and were retried


async def test_gigsim_down_reports_marketplace_unavailable(tmp_path: Path) -> None:
    http = await gigsim_client(tmp_path, faults=True, fault_rate=1.0)
    async with open_session(tmp_path, http) as session:
        assert (await error_of(session, "get_connects_balance")).startswith(
            "marketplace_unavailable")
    assert len(SLEEPS) == gigsim_adapter.MAX_ATTEMPTS - 1


async def test_gigsim_429_honours_retry_after(tmp_path: Path) -> None:
    http = await gigsim_client(tmp_path, rate_limit=RateLimit(capacity=1, refill_per_second=0.5))
    async with open_session(tmp_path, http) as session:
        await call(session, "get_connects_balance")  # GigSim's bucket is now empty
        await error_of(session, "get_connects_balance")  # the bucket never refills: no real time
    assert SLEEPS and all(0 < wait <= gigsim_adapter.MAX_RETRY_AFTER_S for wait in SLEEPS)


async def test_server_rate_limit_is_per_user(tmp_path: Path) -> None:
    async with open_session(tmp_path, rate_per_minute=2) as session:
        await call(session, "get_connects_balance")
        await call(session, "get_connects_balance")
        assert (await error_of(session, "get_connects_balance")).startswith("rate_limited")


class UserEcho:
    """A stub port that answers with the user it was built for."""

    def __init__(self, user: str) -> None:
        self.user = user

    async def get_connects_balance(self) -> dict[str, Any]:
        return {"user_id": self.user, "balance": 1}


HTTP_HEADERS = {"Accept": "application/json, text/event-stream"}
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
BALANCE = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
           "params": {"name": "get_connects_balance", "arguments": {}}}


def open_http_session(client: TestClient, token: str) -> dict[str, str]:
    headers = HTTP_HEADERS | {"Authorization": f"Bearer {token}"}
    response = client.post("/mcp", json=INIT, headers=headers)
    assert response.status_code == 200
    headers["mcp-session-id"] = response.headers["mcp-session-id"]
    client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                headers=headers)
    return headers


def balance_user(client: TestClient, headers: dict[str, str]) -> str | None:
    response = client.post("/mcp", json=BALANCE, headers=headers)
    if response.status_code != 200:
        return None
    data = next(line for line in response.text.splitlines() if line.startswith("data:"))
    result = json.loads(data.removeprefix("data:"))["result"]
    return None if result.get("isError") else result["structuredContent"]["user_id"]


def test_http_maps_each_bearer_token_to_its_own_user(tmp_path: Path) -> None:
    settings = ServerSettings(mcp_tokens={"token-a": "ai_ml_engineer", "token-b": "data_analyst"},
                              stdio_user="fullstack_dev", audit_path=tmp_path / "audit.jsonl")
    server = create_server(settings, port_for=UserEcho)
    with TestClient(server.streamable_http_app(), base_url="http://localhost:8082") as client:
        assert client.post("/mcp", json=INIT, headers=HTTP_HEADERS).status_code == 401
        wrong = HTTP_HEADERS | {"Authorization": "Bearer nope"}
        assert client.post("/mcp", json=INIT, headers=wrong).status_code == 401
        session_a = open_http_session(client, "token-a")
        session_b = open_http_session(client, "token-b")
        assert balance_user(client, session_a) == "ai_ml_engineer"
        assert balance_user(client, session_b) == "data_analyst"
        # B's token on A's session must never act as A.
        hijack = session_a | {"Authorization": "Bearer token-b"}
        assert balance_user(client, hijack) in (None, "data_analyst")
