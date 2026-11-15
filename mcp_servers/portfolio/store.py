"""The signed-in user's portfolio: their folder, their evidence index (built once), lookups."""

import asyncio
import re
from pathlib import Path

from mcp.server.fastmcp.exceptions import ToolError

from mcp_servers.common import REPO_ROOT, HttpSettings, session_user
from rag.index.embedder import Embedder
from rag.index.memory import MemoryIndex, build_index
from rag.ingest.portfolio import EvidenceItem, EvidenceType, load_portfolio

USER = re.compile(r"^[a-z0-9_]+$")  # a user is a folder name under personas_dir


class PortfolioSettings(HttpSettings):
    personas_dir: Path = REPO_ROOT / "data" / "personas"
    cache_dir: Path | None = REPO_ROOT / "data" / "processed" / "embeddings"
    public_url: str = "http://localhost:8083"
    port: int = 8083


class PortfolioStore:
    def __init__(self, settings: PortfolioSettings, embedder: Embedder) -> None:
        self.settings = settings
        self.embedder = embedder
        self._indexes: dict[str, MemoryIndex] = {}
        self._lock = asyncio.Lock()

    def user_dir(self) -> Path:
        """The caller's portfolio folder; the user comes from the session, never an argument."""
        user = session_user(self.settings)
        if not user or not USER.match(user) or not (self.settings.personas_dir / user).is_dir():
            raise ToolError("unauthenticated: no portfolio for this session")
        return self.settings.personas_dir / user

    async def index(self) -> MemoryIndex:
        persona_dir = self.user_dir()
        async with self._lock:  # build each user's index once, off the event loop
            if persona_dir.name not in self._indexes:
                items = await asyncio.to_thread(load_portfolio, persona_dir)
                self._indexes[persona_dir.name] = await asyncio.to_thread(
                    build_index, items, self.embedder, self.settings.cache_dir)
            return self._indexes[persona_dir.name]

    async def find(self, item_id: str, item_type: EvidenceType) -> EvidenceItem | None:
        return next((item for item in (await self.index()).items
                     if item.id == item_id and item.type == item_type), None)
