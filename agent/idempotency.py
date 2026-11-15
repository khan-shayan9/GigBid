"""Idempotency keys for marketplace writes: the same parts always give the same key.

The Marketplace MCP server accepts only `[A-Za-z0-9._:-]` (8-200 chars), while thread, job and
message ids may hold other characters (GigSim message ids contain `_`), so the parts are hashed.
"""

import hashlib

DIGEST_CHARS = 40


def idempotency_key(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:DIGEST_CHARS]
    return f"{prefix}-{digest}"
