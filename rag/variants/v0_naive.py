"""V0: the mandatory baseline, dense top-k cosine over fixed chunks, no rewriting or reranking."""

from collections.abc import Collection

from rag.index.corpus import Corpus


def dense(corpus: Corpus, query: str, chunk_ids: Collection[str],
          depth: int) -> list[tuple[str, float]]:
    """The `depth` chunks most similar to the query, best first, as (chunk id, cosine)."""
    vector = corpus.index.embedder.embed_query(query)
    return corpus.index.search(corpus.persona, vector, depth, chunk_ids)
