"""V0: the mandatory baseline, dense top-k cosine retrieval with no rewriting or reranking."""

import numpy as np

from rag.index.memory import MemoryIndex
from rag.ingest.portfolio import EvidenceItem, EvidenceType, Outcome


def retrieve(query: str, index: MemoryIndex, k: int = 5,
             types: list[EvidenceType] | None = None,
             outcomes: list[Outcome] | None = None) -> list[tuple[EvidenceItem, float]]:
    """The k items most similar to the query, best first, after the metadata filters."""
    scores = index.vectors @ index.embedder.embed_query(query)  # unit vectors: dot = cosine
    allowed = [position for position, item in enumerate(index.items)
               if (not types or item.type in types)
               and (not outcomes or item.outcome in outcomes)]
    best = sorted(allowed, key=lambda position: -scores[position])[:k]
    return [(index.items[position], float(np.round(scores[position], 4))) for position in best]
