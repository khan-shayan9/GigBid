"""The retriever: one pipeline assembled from the variant switches in `rag.variants` (config).

A variant is a set of switches over the components in rag/variants/:
  decompose (V1) -> first stage: dense (V0) or hybrid (V2) -> rerank (V3) -> corrective (V8).
`RAG_VARIANT` overrides `rag.variant`. Results are evidence items (chunks folded into their
item, best chunk wins), so cited ids stay item ids.
"""

import os
from collections.abc import Callable, Collection

from pydantic import BaseModel

from rag.index.corpus import Corpus
from rag.ingest.portfolio import EvidenceItem
from rag.variants.v0_naive import dense
from rag.variants.v1_decompose import Complete, decompose, visible
from rag.variants.v2_hybrid import hybrid
from rag.variants.v3_rerank import Reranker, rerank
from rag.variants.v8_corrective import corrective

Allowed = Callable[[EvidenceItem], bool]
Hits = list[tuple[EvidenceItem, float]]


class VariantSettings(BaseModel):
    decompose: bool = False
    hybrid: bool = False
    rerank: bool = False
    corrective: bool = False


class Retriever:
    def __init__(self, rag_config: dict, variant: str | None = None,
                 reranker: Reranker | None = None, complete: Complete | None = None,
                 prompts: dict[str, str] | None = None) -> None:
        """`complete` and `prompts` ("decompose", "rewrite") are needed by V1 and V8 only.

        Missing parts are reported when a search needs them, so a server that only lists its
        tools (contract tests) starts without a reranker.
        """
        self.name = variant or os.environ.get("RAG_VARIANT") or rag_config["variant"]
        self.settings = VariantSettings(**rag_config["variants"][self.name])
        self.config = rag_config
        self.reranker = reranker
        self.complete = complete
        self.prompts = prompts or {}

    def search(self, corpus: Corpus, query: str, k: int, allowed: Allowed) -> Hits:
        """Evidence items for one query (one requirement), best first.

        The query is one requirement, so V1's split does not apply here (see `search_job`).
        """
        if (self.settings.rerank or self.settings.corrective) and self.reranker is None:
            raise ValueError(f"variant {self.name} needs a reranker")
        chunk_ids = corpus.chunk_ids(allowed)
        if self.settings.corrective:
            hits = corrective(query, lambda text: self._ranked(corpus, text, chunk_ids),
                              self._rewrite if self.complete and "rewrite" in self.prompts
                              else None, **self.config["corrective"])
        else:
            hits = self._ranked(corpus, query, chunk_ids)
        return self._items(corpus, hits, k)

    def search_job(self, corpus: Corpus, post: str, k: int, allowed: Allowed) -> Hits:
        """Evidence items for a whole job post: as one query, or one per requirement (V1)."""
        if not self.settings.decompose:
            return self.search(corpus, post, k, allowed)
        if self.complete is None or "decompose" not in self.prompts:
            raise ValueError(f"variant {self.name} needs a model and the decompose prompt")
        rankings = [self.search(corpus, requirement, k, allowed)
                    for requirement in self.requirements(post)]
        # Round-robin by rank: each requirement's best item first. RRF here would favour
        # generic items that rank moderately for every requirement over the best per requirement.
        merged: dict[str, float] = {}
        for rank in range(k):
            for ranking in rankings:
                if rank < len(ranking):
                    merged.setdefault(ranking[rank][0].id, round(1 / (rank + 1), 4))
        return [(corpus.items[item_id], score) for item_id, score in merged.items()][:k]

    def requirements(self, post: str) -> list[str]:
        return decompose(post, self.complete, self.prompts["decompose"]) \
            if self.settings.decompose and self.complete else [post]

    def _ranked(self, corpus: Corpus, query: str,
                chunk_ids: Collection[str]) -> list[tuple[str, float]]:
        depth = self.config["candidates"]
        ranked = hybrid(corpus, query, chunk_ids, depth, self.config["rrf_k"]) \
            if self.settings.hybrid else dense(corpus, query, chunk_ids, depth)
        if self.settings.rerank:
            ranked = rerank(self.reranker, corpus, query, ranked, self.config["rerank_depth"])
        return ranked

    def _rewrite(self, query: str) -> str:
        return visible(self.complete(self.prompts["rewrite"].format(query=query))) or query

    @staticmethod
    def _items(corpus: Corpus, hits: list[tuple[str, float]], k: int) -> Hits:
        best: dict[str, float] = {}
        for chunk_id, score in hits:
            best.setdefault(corpus.chunks[chunk_id].item_id, score)
        return [(corpus.items[item_id], round(score, 4)) for item_id, score in best.items()][:k]
