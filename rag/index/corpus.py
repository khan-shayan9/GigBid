"""One persona's searchable corpus: items, their chunks, the vector index and BM25.

`load_corpus` is also the incremental re-index: run it again after the user adds or edits work,
and only new or changed chunks are embedded; removed ones leave the index.
"""

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np

from rag.index.bm25 import BM25
from rag.index.embedder import Embedder
from rag.index.memory import MemoryIndex
from rag.ingest.chunking import Chunk, chunk_items
from rag.ingest.portfolio import EvidenceItem, load_portfolio


class VectorIndex(Protocol):
    embedder: Embedder

    def sync(self, persona: str, chunks: list[Chunk],
             metadata: dict[str, dict] | None = None) -> dict[str, int]: ...

    def search(self, persona: str, query: np.ndarray, k: int,
               chunk_ids: object) -> list[tuple[str, float]]: ...


@dataclass
class Corpus:
    persona: str
    items: dict[str, EvidenceItem]
    chunks: dict[str, Chunk]
    index: VectorIndex
    bm25: BM25
    last_sync: dict[str, int] = field(default_factory=dict)

    def chunk_ids(self, allowed: Callable[[EvidenceItem], bool]) -> set[str]:
        return {chunk.id for chunk in self.chunks.values() if allowed(self.items[chunk.item_id])}


def make_index(rag_config: dict, embedder: Embedder, cache_dir: Path | None) -> VectorIndex:
    """The index named by `rag.index` (RAG_INDEX overrides): memory or pgvector."""
    backend = os.environ.get("RAG_INDEX") or rag_config["index"]
    if backend == "memory":
        return MemoryIndex(embedder, cache_dir)
    if backend == "pgvector":
        from rag.index.pgvector import PgVectorIndex  # psycopg loads only when used

        return PgVectorIndex(embedder, os.environ["DATABASE_URL"])
    raise ValueError(f"unknown rag index {backend!r}")


def load_corpus(persona_dir: Path, index: VectorIndex, rag_config: dict,
                items: list[EvidenceItem] | None = None) -> Corpus:
    """Load (or reload) a persona's portfolio and sync its chunks into the index."""
    items = items if items is not None else load_portfolio(persona_dir)
    chunks = chunk_items(items, rag_config["chunk_words"], rag_config["chunk_overlap"])
    metadata = {item.id: item.model_dump(exclude={"text"}) for item in items}
    report = index.sync(persona_dir.name, chunks, metadata)
    return Corpus(persona=persona_dir.name, items={item.id: item for item in items},
                  chunks={chunk.id: chunk for chunk in chunks}, index=index,
                  bm25=BM25([chunk.id for chunk in chunks], [chunk.text for chunk in chunks]),
                  last_sync=report)
