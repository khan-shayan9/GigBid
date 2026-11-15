"""In-memory vector index over evidence items, with an on-disk embedding cache.

shortcut: vectors live in a NumPy matrix in process memory; Phase 4 moves them to pgvector
(docs/adr/0001-vector-store-pgvector.md).
"""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from rag.index.embedder import Embedder
from rag.ingest.portfolio import EvidenceItem


@dataclass(frozen=True)
class MemoryIndex:
    items: list[EvidenceItem]
    vectors: np.ndarray  # one unit-length row per item
    embedder: Embedder


def build_index(items: list[EvidenceItem], embedder: Embedder,
                cache_dir: Path | None = None) -> MemoryIndex:
    """Embed every item, reusing vectors cached for the same model and the same text."""
    keys = [hashlib.sha256(item.text.encode()).hexdigest() for item in items]
    cache_path = cache_dir / f"{re.sub(r'[^A-Za-z0-9]+', '-', embedder.model_id)}.npz" \
        if cache_dir else None
    cache = dict(np.load(cache_path)) if cache_path and cache_path.exists() else {}
    missing = [index for index, key in enumerate(keys) if key not in cache]
    if missing:
        fresh = embedder.embed_documents([items[index].text for index in missing])
        cache.update({keys[index]: vector for index, vector in zip(missing, fresh, strict=True)})
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez(cache_path, **cache)
    return MemoryIndex(items, np.stack([cache[key] for key in keys]), embedder)
