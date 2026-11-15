"""Bearer-token auth and a per-user rate limiter shared by our MCP servers' HTTP endpoints."""

import hmac
import time

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken


def parse_tokens(raw: str, env_name: str) -> dict[str, str]:
    """Parse 'user=token,user=token' into {token: user}."""
    tokens: dict[str, str] = {}
    for pair in filter(None, (part.strip() for part in raw.split(","))):
        user_id, _, token = pair.partition("=")
        if not user_id or not token or token in tokens:
            raise ValueError(f"{env_name}: empty or reused token for {user_id!r}")
        tokens[token] = user_id
    return tokens


class StaticTokenVerifier:
    """Static per-user Bearer tokens from the environment (no OAuth server of our own)."""

    def __init__(self, tokens: dict[str, str]) -> None:
        self._tokens = tokens

    async def verify_token(self, token: str) -> AccessToken | None:
        for known, user_id in self._tokens.items():
            if hmac.compare_digest(known.encode(), token.encode()):
                return AccessToken(token=token, client_id=user_id, scopes=[])
        return None


def http_user() -> str | None:
    """The user behind the current HTTP request's Bearer token (None on stdio or in memory)."""
    access = get_access_token()
    return access.client_id if access else None


class RateLimiter:
    """Token bucket per user: `per_minute` calls a minute, bursts up to the same number."""

    def __init__(self, per_minute: int) -> None:
        self._capacity = float(per_minute)
        self._refill_per_s = per_minute / 60
        self._buckets: dict[str, tuple[float, float]] = {}

    def retry_after(self, user_id: str) -> float:
        """Take one call; return 0 if allowed, else the seconds until the next call is."""
        now = time.monotonic()
        tokens, last = self._buckets.get(user_id, (self._capacity, now))
        tokens = min(self._capacity, tokens + (now - last) * self._refill_per_s)
        if tokens >= 1:
            self._buckets[user_id] = (tokens - 1, now)
            return 0.0
        self._buckets[user_id] = (tokens, now)
        return (1 - tokens) / self._refill_per_s
