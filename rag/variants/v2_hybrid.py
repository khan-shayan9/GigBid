"""V2: BM25 plus dense, fused with reciprocal rank fusion (Cormack et al., 2009)."""

from collections.abc import Collection

from rag.index.corpus import Corpus
from rag.variants.v0_naive import dense


def rrf(rankings: list[list[str]], k: int) -> list[tuple[str, float]]:
    """Fuse ranked id lists: each id scores the sum of 1 / (k + rank) over the lists."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: -pair[1])


def hybrid(corpus: Corpus, query: str, chunk_ids: Collection[str], depth: int,
           rrf_k: int) -> list[tuple[str, float]]:
    dense_ids = [chunk_id for chunk_id, _ in dense(corpus, query, chunk_ids, depth)]
    bm25_ids = [chunk_id for chunk_id, _ in corpus.bm25.search(query, chunk_ids, depth)]
    return rrf([dense_ids, bm25_ids], rrf_k)[:depth]
