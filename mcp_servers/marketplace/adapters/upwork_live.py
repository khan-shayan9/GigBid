"""MarketplacePort over Upwork's official MCP server (live mode), with per-user OAuth 2.1.

The server (https://mcp.upwork.com/mcp) is OAuth-protected: PKCE S256 and dynamic client
registration through Upwork's authorize and token endpoints. The MCP SDK's OAuthClientProvider
runs that flow; tokens live encrypted per user in apps/api/auth/token_store.py.

shortcut: Upwork's tool names and fields are only visible after a real sign-in, so the port
method -> tool map in agent/config.yaml (`marketplace.upwork_live.tools`) starts empty and
arguments and results pass through unchanged. After `login` prints the tool list, fill the map
and add field mapping per tool. Until then every unmapped call fails with `not_mapped`.

Live mode never submits or sends: proposals and messages are created only as drafts that the
user confirms on Upwork (3.AI_RULES.md §15).

Sign in once per user (user-owned task): `python -m mcp_servers.marketplace.adapters.upwork_live
login --user <user>`.
"""

import argparse
import asyncio
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.shared.auth import OAuthClientMetadata
from pydantic import AnyUrl

from agent.config import load_config
from agent.marketplace_port import MarketplaceError, MarketplaceUnavailable
from apps.api.auth.token_store import EncryptedTokenStore

REDIRECT_URI = "http://localhost:8765/callback"
CALL_TIMEOUT_S = 30.0
TOKEN_DIR = Path(__file__).resolve().parents[3] / "data" / "processed" / "oauth"


def client_metadata() -> OAuthClientMetadata:
    return OAuthClientMetadata(client_name="GigBid", redirect_uris=[AnyUrl(REDIRECT_URI)],
                               grant_types=["authorization_code", "refresh_token"],
                               response_types=["code"], token_endpoint_auth_method="none")


async def _needs_login(*_: object) -> Any:
    raise MarketplaceError(401, "upwork_login_required",
                           "run the upwork_live login command for this user first")


def oauth(url: str, storage: TokenStorage,
          redirect: Callable[[str], Awaitable[None]] = _needs_login,
          callback: Callable[[], Awaitable[tuple[str, str | None]]] = _needs_login,
          ) -> OAuthClientProvider:
    return OAuthClientProvider(url, client_metadata(), storage, redirect, callback)


class UpworkLiveAdapter:
    def __init__(self, url: str, tools: dict[str, str | None], auth: httpx.Auth,
                 storage: TokenStorage) -> None:
        self._tools = tools
        self._storage = storage
        self._client = MultiServerMCPClient(
            {"upwork": {"transport": "streamable_http", "url": url, "auth": auth}})

    async def _call(self, method: str, args: dict[str, Any]) -> dict[str, Any]:
        tool = self._tools.get(method)
        if not tool:
            raise MarketplaceError(501, "not_mapped", f"no Upwork tool mapped for {method}")
        # Check before connecting: without tokens the OAuth flow would register a client with
        # Upwork and then stop at the browser step, deep inside the transport.
        if not await self._storage.get_tokens():
            raise MarketplaceError(401, "upwork_login_required",
                                   "run the upwork_live login command for this user first")
        try:
            async with asyncio.timeout(CALL_TIMEOUT_S),                     self._client.session("upwork") as session:
                result = await session.call_tool(tool, {k: v for k, v in args.items()
                                                        if v not in (None, "", [])})
        except (httpx.HTTPError, OSError, TimeoutError) as error:
            raise MarketplaceUnavailable(f"Upwork MCP: {type(error).__name__}") from error
        if result.isError:
            text = result.content[0].text if result.content else "error"
            raise MarketplaceError(502, "upwork_error", text)
        return result.structuredContent or {}

    async def search_jobs(self, query: str = "", skills: list[str] | None = None,
                          payment_type: str | None = None, since: str | None = None,
                          limit: int = 20, offset: int = 0) -> dict[str, Any]:
        return await self._call("search_jobs", {
            "query": query, "skills": skills, "payment_type": payment_type, "since": since,
            "limit": limit, "offset": offset})

    async def get_job(self, job_id: str) -> dict[str, Any]:
        return await self._call("get_job", {"job_id": job_id})

    async def get_client_history(self, client_id: str) -> dict[str, Any]:
        return await self._call("get_client_history", {"client_id": client_id})

    async def get_connects_balance(self) -> dict[str, Any]:
        return await self._call("get_connects_balance", {})

    async def get_market_rates(self) -> dict[str, Any]:
        raise MarketplaceError(501, "not_available_live", "Upwork serves no market-rate stats")

    async def list_messages(self, thread_id: str | None = None, since: str | None = None,
                            limit: int = 100) -> dict[str, Any]:
        return await self._call("list_messages",
                                {"thread_id": thread_id, "since": since, "limit": limit})

    async def create_proposal_draft(self, payload: dict[str, Any], idempotency_key: str,
                                    dry_run: bool) -> dict[str, Any]:
        if dry_run:
            raise MarketplaceError(501, "no_dry_run_live", "Upwork has no proposal preview")
        return await self._call("create_proposal_draft", payload)

    async def submit_proposal(self, proposal_id: str, idempotency_key: str,
                              dry_run: bool) -> dict[str, Any]:
        raise MarketplaceError(403, "submit_on_upwork",
                               "live mode only drafts; the user submits on Upwork")

    async def send_message(self, thread_id: str, text: str, idempotency_key: str,
                           dry_run: bool) -> dict[str, Any]:
        raise MarketplaceError(403, "send_on_upwork",
                               "live mode only drafts; the user sends on Upwork")


def adapter_for(user: str) -> UpworkLiveAdapter:
    settings = load_config()["marketplace"]["upwork_live"]
    store = EncryptedTokenStore(user, TOKEN_DIR, os.environ["TOKEN_ENCRYPTION_KEY"])
    return UpworkLiveAdapter(settings["url"], settings["tools"], oauth(settings["url"], store),
                             store)


async def login(user: str) -> None:
    """Interactive sign-in: open the printed URL, approve, paste the address you land on."""
    settings = load_config()["marketplace"]["upwork_live"]
    store = EncryptedTokenStore(user, TOKEN_DIR, os.environ["TOKEN_ENCRYPTION_KEY"])

    async def show(url: str) -> None:
        print(f"Open this URL, approve GigBid, then copy the address you are sent to:\n{url}")

    async def ask() -> tuple[str, str | None]:
        query = parse_qs(urlparse(input("Paste the full redirect address: ").strip()).query)
        return query["code"][0], query.get("state", [None])[0]

    client = MultiServerMCPClient({"upwork": {"transport": "streamable_http",
                                              "url": settings["url"],
                                              "auth": oauth(settings["url"], store, show, ask)}})
    async with client.session("upwork") as session:
        tools = (await session.list_tools()).tools
    print("Signed in. Upwork tools (map them in agent/config.yaml):")
    for tool in tools:
        print(f"- {tool.name}: {(tool.description or '').splitlines()[0][:100]}")


if __name__ == "__main__":
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["login"])
    parser.add_argument("--user", required=True)
    asyncio.run(login(parser.parse_args().user))
