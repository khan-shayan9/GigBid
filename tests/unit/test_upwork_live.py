"""Live-mode adapter and the encrypted OAuth token store, without a real Upwork account."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import Fernet, InvalidToken
from mcp.shared.auth import OAuthToken
from mcp.types import CallToolResult

from agent.marketplace_port import MarketplaceError
from apps.api.auth.token_store import EncryptedTokenStore
from mcp_servers.marketplace.adapters.upwork_live import UpworkLiveAdapter, oauth

KEY = Fernet.generate_key().decode()
SECRET = "access-token-that-must-not-leak"


async def test_tokens_are_encrypted_per_user(tmp_path: Path) -> None:
    store = EncryptedTokenStore("ai_ml_engineer", tmp_path, KEY)
    await store.set_tokens(OAuthToken(access_token=SECRET, token_type="Bearer"))
    assert (await store.get_tokens()).access_token == SECRET
    assert SECRET.encode() not in (tmp_path / "ai_ml_engineer.oauth.enc").read_bytes()
    assert await EncryptedTokenStore("data_analyst", tmp_path, KEY).get_tokens() is None
    with pytest.raises(InvalidToken):
        await EncryptedTokenStore("ai_ml_engineer", tmp_path, Fernet.generate_key().decode()
                                  ).get_tokens()
    with pytest.raises(ValueError):
        EncryptedTokenStore("../ai_ml_engineer", tmp_path, KEY)


def adapter(tmp_path: Path, tools: dict[str, str | None], calls: list) -> UpworkLiveAdapter:
    store = EncryptedTokenStore("ai_ml_engineer", tmp_path, KEY)
    live = UpworkLiveAdapter("https://upwork.invalid/mcp", tools,
                             oauth("https://upwork.invalid/mcp", store), store)

    class FakeSession:
        async def call_tool(self, name: str, args: dict[str, Any]) -> CallToolResult:
            calls.append((name, args))
            return CallToolResult(content=[], structuredContent={"jobs": [], "total": 0})

    @asynccontextmanager
    async def session(name: str):
        yield FakeSession()

    live._client.session = session  # type: ignore[method-assign]
    return live


async def test_no_tokens_means_login_required_without_connecting(tmp_path: Path) -> None:
    calls: list = []
    live = adapter(tmp_path, {"search_jobs": "upwork__search_jobs"}, calls)
    with pytest.raises(MarketplaceError) as error:
        await live.search_jobs("rag")
    assert error.value.code == "upwork_login_required" and calls == []


async def test_mapped_reads_reach_the_upwork_tool(tmp_path: Path) -> None:
    calls: list = []
    await EncryptedTokenStore("ai_ml_engineer", tmp_path, KEY).set_tokens(
        OAuthToken(access_token=SECRET, token_type="Bearer"))
    live = adapter(tmp_path, {"search_jobs": "upwork__search_jobs"}, calls)
    assert await live.search_jobs("rag", limit=5) == {"jobs": [], "total": 0}
    assert calls == [("upwork__search_jobs", {"query": "rag", "limit": 5, "offset": 0})]


async def test_live_mode_never_submits_or_sends(tmp_path: Path) -> None:
    calls: list = []
    live = adapter(tmp_path, {"get_job": None}, calls)
    for action, code in [(live.get_job("j1"), "not_mapped"),
                         (live.submit_proposal("p1", "key-0001", False), "submit_on_upwork"),
                         (live.send_message("t1", "hi", "key-0002", False), "send_on_upwork"),
                         (live.create_proposal_draft({}, "key-0003", True), "no_dry_run_live")]:
        with pytest.raises(MarketplaceError) as error:
            await action
        assert error.value.code == code
    assert calls == []
