"""What every GigBid MCP server shares: settings, auth wiring, the session's user, and startup."""

import os
import sys
from collections.abc import Callable
from pathlib import Path

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from mcp_servers.auth import StaticTokenVerifier, http_user, parse_tokens

# Data paths are anchored here so a server started from any folder finds the same files.
REPO_ROOT = Path(__file__).resolve().parents[1]


class HttpSettings(BaseModel):
    mcp_tokens: dict[str, str] = {}  # MCP Bearer token -> user
    public_url: str
    host: str = "127.0.0.1"
    port: int
    stdio_user: str | None = None  # the user for stdio and in-memory sessions (no Bearer token)


def new_server(name: str, instructions: str, settings: HttpSettings) -> FastMCP:
    """With `mcp_tokens` every call needs a Bearer token; without them every call is `stdio_user`."""
    if not settings.mcp_tokens:
        return FastMCP(name, host=settings.host, port=settings.port, instructions=instructions)
    auth = AuthSettings(issuer_url=settings.public_url, resource_server_url=settings.public_url,
                        validate_token_resource=False)
    return FastMCP(name, host=settings.host, port=settings.port, instructions=instructions,
                   auth=auth, token_verifier=StaticTokenVerifier(settings.mcp_tokens))


def session_user(settings: HttpSettings) -> str | None:
    # Never fall back to the stdio user on the authenticated transport.
    return http_user() if settings.mcp_tokens else settings.stdio_user


def http_settings_from_env(prefix: str, default_url: str, default_port: int) -> dict:
    """The HttpSettings fields from `<prefix>_MCP_TOKENS`, `<prefix>_PUBLIC_URL` and the rest."""
    env = os.environ
    return {
        "mcp_tokens": parse_tokens(env.get(f"{prefix}_MCP_TOKENS", ""), f"{prefix}_MCP_TOKENS"),
        "public_url": env.get(f"{prefix}_PUBLIC_URL", default_url),
        "host": env.get(f"{prefix}_HOST", "127.0.0.1"),
        "port": int(env.get(f"{prefix}_PORT", str(default_port))),
        "stdio_user": env.get(f"{prefix}_STDIO_USER") or None,
    }


def serve(settings: HttpSettings, build: Callable[[HttpSettings], FastMCP], prefix: str) -> None:
    """`http` argument: Streamable HTTP with Bearer auth; otherwise stdio for one local user."""
    if sys.argv[1:] == ["http"]:
        if not settings.mcp_tokens:
            sys.exit(f"{prefix}_MCP_TOKENS must be set: the HTTP endpoint never runs without auth")
        build(settings.model_copy(update={"stdio_user": None})).run("streamable-http")
    else:
        build(settings.model_copy(update={"mcp_tokens": {}})).run()
