"""The signed-in user's portfolio: their folder, their searchable corpus (built once), lookups."""

import asyncio
import re
from pathlib import Path

from mcp.server.fastmcp.exceptions import ToolError

from mcp_servers.common import REPO_ROOT, HttpSettings, session_user
from rag.index.corpus import Corpus, VectorIndex, load_corpus
from rag.ingest.portfolio import EvidenceItem, EvidenceType
from rag.retriever import Retriever

USER = re.compile(r"^[a-z0-9_]+$")  # a user is a folder name under personas_dir


class PortfolioSettings(HttpSettings):
    personas_dir: Path = REPO_ROOT / "data" / "personas"
    cache_dir: Path | None = REPO_ROOT / "data" / "processed" / "embeddings"
    public_url: str = "http://localhost:8083"
    port: int = 8083


class PortfolioStore:
    def __init__(self, settings: PortfolioSettings, index: VectorIndex, rag_config: dict,
                 retriever: Retriever) -> None:
        self.settings = settings
        self.index = index
        self.rag_config = rag_config
        self.retriever = retriever
        self._corpora: dict[str, Corpus] = {}
        self._lock = asyncio.Lock()

    def user_dir(self) -> Path:
        """The caller's portfolio folder; the user comes from the session, never an argument."""
        user = session_user(self.settings)
        if not user or not USER.match(user) or not (self.settings.personas_dir / user).is_dir():
            raise ToolError("unauthenticated: no portfolio for this session")
        return self.settings.personas_dir / user

    async def corpus(self) -> Corpus:
        persona_dir = self.user_dir()
        async with self._lock:  # build each user's corpus once, off the event loop
            if persona_dir.name not in self._corpora:
                self._corpora[persona_dir.name] = await asyncio.to_thread(
                    load_corpus, persona_dir, self.index, self.rag_config)
            return self._corpora[persona_dir.name]

    async def reindex(self) -> dict[str, int]:
        """Re-read the caller's folder after they add or edit work; embeds only what changed."""
        persona_dir = self.user_dir()
        async with self._lock:
            corpus = await asyncio.to_thread(load_corpus, persona_dir, self.index,
                                             self.rag_config)
            self._corpora[persona_dir.name] = corpus
            return corpus.last_sync

    async def find(self, item_id: str, item_type: EvidenceType) -> EvidenceItem | None:
        item = (await self.corpus()).items.get(item_id)
        return item if item and item.type == item_type else None
