"""In-process vector index with an on-disk embedding cache: for local evals and tests.

It runs the same exact cosine search as the pgvector backend (rag/index/pgvector.py), which
docker compose and CI use. Local evaluation uses this one because the dev laptop has no Postgres.
"""

import hashlib
import re
from collections.abc import Collection
from pathlib import Path

import numpy as np

from rag.index.embedder import Embedder
from rag.ingest.chunking import Chunk


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def sync_report(old: dict[str, str], new: dict[str, str]) -> dict[str, int]:
    """Counts of added, updated, removed and unchanged chunks between two {id: hash} maps."""
    return {"added": len(new.keys() - old.keys()),
            "updated": sum(old[key] != new[key] for key in new.keys() & old.keys()),
            "removed": len(old.keys() - new.keys()),
            "unchanged": sum(old[key] == new[key] for key in new.keys() & old.keys())}


class MemoryIndex:
    def __init__(self, embedder: Embedder, cache_dir: Path | None = None) -> None:
        self.embedder = embedder
        self.cache_dir = cache_dir
        self.embedded = 0  # texts sent to the embedder; tests use it to check incremental sync
        self._hashes: dict[str, dict[str, str]] = {}  # persona -> chunk id -> content hash
        self._vectors: dict[str, dict[str, np.ndarray]] = {}  # persona -> chunk id -> vector

    def sync(self, persona: str, chunks: list[Chunk],
             metadata: dict[str, dict] | None = None) -> dict[str, int]:
        """Make the persona's index match `chunks`, embedding only new or changed text.

        `metadata` is accepted for parity with the pgvector index; items keep it in memory.
        """
        old = self._hashes.get(persona, {})
        new = {chunk.id: content_hash(chunk.text) for chunk in chunks}
        changed = [chunk for chunk in chunks if old.get(chunk.id) != new[chunk.id]]
        fresh = dict(zip((chunk.id for chunk in changed),
                         self._embed([chunk.text for chunk in changed]), strict=True))
        vectors = self._vectors.get(persona, {})
        self._vectors[persona] = {chunk.id: fresh.get(chunk.id, vectors.get(chunk.id))
                                  for chunk in chunks}
        self._hashes[persona] = new
        return sync_report(old, new)

    def search(self, persona: str, query: np.ndarray, k: int,
               chunk_ids: Collection[str]) -> list[tuple[str, float]]:
        """The k chunks among `chunk_ids` most similar to the query (unit vectors), best first."""
        vectors = self._vectors.get(persona, {})
        # Sorted, so ties break by id on every run, as in the pgvector index's ORDER BY.
        ids = sorted(chunk_id for chunk_id in chunk_ids if chunk_id in vectors)
        if not ids:
            return []
        scores = np.stack([vectors[chunk_id] for chunk_id in ids]) @ query
        best = np.argsort(-scores, kind="stable")[:k]
        return [(ids[position], float(scores[position])) for position in best]

    def _embed(self, texts: list[str]) -> list[np.ndarray]:
        """Embed texts, reusing vectors cached on disk for the same model and the same text."""
        if not texts:
            return []
        keys = [content_hash(text) for text in texts]
        name = re.sub(r"[^A-Za-z0-9]+", "-", self.embedder.model_id)
        path = self.cache_dir / f"{name}.npz" if self.cache_dir else None
        cache = dict(np.load(path)) if path and path.exists() else {}
        missing = sorted({key: text for key, text in zip(keys, texts, strict=True)
                          if key not in cache}.items())
        if missing:
            self.embedded += len(missing)
            vectors = self.embedder.embed_documents([text for _, text in missing])
            cache.update({key: vector for (key, _), vector in zip(missing, vectors, strict=True)})
            if path:
                path.parent.mkdir(parents=True, exist_ok=True)
                np.savez(path, **cache)
        return [cache[key] for key in keys]
