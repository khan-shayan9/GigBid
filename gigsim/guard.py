"""Request guard: Bearer auth, per-user rate limit (429 + Retry-After) and seeded 5xx faults."""

import hashlib
import hmac
import math
import threading
import time

from fastapi import HTTPException, Request

from gigsim.settings import Settings


def api_error(
    status: int, code: str, message: str, headers: dict[str, str] | None = None
) -> HTTPException:
    return HTTPException(status, detail={"code": code, "message": message}, headers=headers)


class TokenBucket:
    def __init__(self, capacity: int, refill_per_second: float) -> None:
        self._capacity = capacity
        self._refill = refill_per_second
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()

    def take(self, user_id: str) -> float | None:
        """Take one token; return None if allowed, else seconds until a token is free."""
        with self._lock:
            now = time.monotonic()
            tokens, last = self._buckets.get(user_id, (self._capacity, now))
            tokens = min(self._capacity, tokens + (now - last) * self._refill)
            if tokens >= 1:
                self._buckets[user_id] = (tokens - 1, now)
                return None
            self._buckets[user_id] = (tokens, now)
            return (1 - tokens) / self._refill


def fault_hits(seed: int, user_id: str, signature: str, attempt: int, rate: float) -> bool:
    # Hash on the request itself, not a global counter: parallel callers stay repeatable and each
    # retry of the same request is a fresh draw, so retries converge.
    digest = hashlib.sha256(f"{seed}|{user_id}|{signature}|{attempt}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64 < rate


class Guard:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        limit = settings.config.rate_limit
        self._bucket = TokenBucket(limit.capacity, limit.refill_per_second)
        # shortcut: attempt counts live in memory and grow with distinct requests; fine for one
        # simulator process, bound or persist them if GigSim ever runs long-lived at scale.
        self._attempts: dict[tuple[str, str], int] = {}
        self._lock = threading.Lock()

    def user(self, request: Request) -> str:
        user_id = self._authenticate(request)
        retry_after = self._bucket.take(user_id)
        if retry_after is not None:
            raise api_error(
                429, "rate_limited", "Too many requests.",
                headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
            )
        key = request.headers.get("Idempotency-Key", "")
        self._maybe_fault(user_id, f"{request.method} {request.url.path}?{request.url.query}|{key}")
        return user_id

    def after_commit(self, user_id: str, idempotency_key: str) -> None:
        """A write that succeeded can still answer 5xx; the retry replays the stored result."""
        self._maybe_fault(user_id, f"after-commit|{idempotency_key}")

    def reset(self) -> None:
        with self._lock:
            self._attempts.clear()
        self._bucket.reset()

    def admin(self, request: Request) -> None:
        token = _bearer(request)
        admin_token = self._settings.admin_token
        if not admin_token or not hmac.compare_digest(token.encode(), admin_token.encode()):
            raise api_error(403, "forbidden", "Admin token required.")

    def _authenticate(self, request: Request) -> str:
        user_id = self._settings.tokens.get(_bearer(request))
        if user_id is None:
            raise api_error(401, "unauthenticated", "A valid Bearer token is required.")
        return user_id

    def _maybe_fault(self, user_id: str, signature: str) -> None:
        if not self._settings.faults_enabled:
            return
        with self._lock:
            attempt = self._attempts.get((user_id, signature), 0) + 1
            self._attempts[(user_id, signature)] = attempt
        config = self._settings.config
        if fault_hits(config.random_seed, user_id, signature, attempt, config.fault_rate):
            raise api_error(503, "gigsim_unavailable", "Temporary marketplace error; retry.")


def _bearer(request: Request) -> str:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""
