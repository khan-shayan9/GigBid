"""Per-user OAuth tokens, encrypted at rest (Fernet, key from TOKEN_ENCRYPTION_KEY).

Implements the MCP SDK's TokenStorage, so `OAuthClientProvider` reads and refreshes Upwork tokens
through it. Tokens are never logged or written in plain text.
"""

import json
import re
from pathlib import Path

from cryptography.fernet import Fernet
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

USER = re.compile(r"^[a-z0-9_]+$")


class EncryptedTokenStore:
    def __init__(self, user: str, store_dir: Path, key: str) -> None:
        if not USER.match(user):
            raise ValueError(f"invalid user id {user!r}")
        self._path = store_dir / f"{user}.oauth.enc"
        self._fernet = Fernet(key.encode())

    def _read(self) -> dict:
        if not self._path.exists():
            return {}
        return json.loads(self._fernet.decrypt(self._path.read_bytes()))

    def _write(self, field: str, value: dict) -> None:
        record = self._read() | {field: value}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_bytes(self._fernet.encrypt(json.dumps(record).encode()))

    async def get_tokens(self) -> OAuthToken | None:
        tokens = self._read().get("tokens")
        return OAuthToken.model_validate(tokens) if tokens else None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self._write("tokens", tokens.model_dump(mode="json", exclude_none=True))

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        info = self._read().get("client_info")
        return OAuthClientInformationFull.model_validate(info) if info else None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self._write("client_info", client_info.model_dump(mode="json", exclude_none=True))


def has_tokens(user: str, store_dir: Path) -> bool:
    """Whether `user` has signed in to Upwork (an encrypted token file exists); reads no secret."""
    return bool(USER.match(user)) and (store_dir / f"{user}.oauth.enc").exists()
