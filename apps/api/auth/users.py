"""Accounts and signed session cookies (multi-user sign-in).

Accounts come from APP_USERS as `name=salt:hash` pairs (scrypt), so no password is stored in
plain text. Make a pair with `python -m apps.api.auth.users <name> <password>`.
A session is `name.expiry.signature`, signed with APP_SECRET_KEY (HMAC-SHA256).
shortcut: accounts are env-defined, with no sign-up page; add a users table if self-sign-up is needed.
"""

import hashlib
import hmac
import os
import re
import secrets
import sys
import time

ACCOUNT = re.compile(r"^[a-z0-9_]{1,40}$")  # also the tenant id and the thread-id prefix
SCRYPT = {"n": 2**14, "r": 8, "p": 1}


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **SCRYPT).hex()
    return f"{salt}:{digest}"


def accounts() -> dict[str, str]:
    pairs = [pair.strip() for pair in os.environ.get("APP_USERS", "").split(",") if pair.strip()]
    found = dict(pair.split("=", 1) for pair in pairs)
    bad = [name for name in found if not ACCOUNT.match(name)]
    if bad:
        raise ValueError(f"APP_USERS: invalid account names {bad}")
    return found


def check_password(name: str, password: str) -> bool:
    stored = accounts().get(name)
    if stored is None:
        hash_password(password)  # same work for unknown names, so timing does not tell
        return False
    return hmac.compare_digest(hash_password(password, stored.split(":", 1)[0]), stored)


def _secret() -> bytes:
    secret = os.environ.get("APP_SECRET_KEY", "")
    if len(secret) < 16 or secret == "replace_me":
        raise RuntimeError("APP_SECRET_KEY must be set to a random value of 16+ characters")
    return secret.encode()


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()


def new_session(name: str, hours: float) -> str:
    payload = f"{name}.{int(time.time() + hours * 3600)}"
    return f"{payload}.{_sign(payload)}"


def session_account(token: str) -> str | None:
    """The signed-in account, or None for a missing, forged or expired session."""
    parts = token.split(".")
    if len(parts) != 3 or not parts[1].isdigit():
        return None
    name, expiry, signature = parts
    if not hmac.compare_digest(_sign(f"{name}.{expiry}"), signature):
        return None
    return name if int(expiry) > time.time() and name in accounts() else None


if __name__ == "__main__":
    print(f"{sys.argv[1]}={hash_password(sys.argv[2])}")
