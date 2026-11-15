"""V3: rescore the first-stage candidates with a cross-encoder (open model, run on CPU)."""

from typing import Protocol

from rag.index.bm25 import tokens
from rag.index.corpus import Corpus


class Reranker(Protocol):
    model_id: str

    def score(self, query: str, texts: list[str]) -> list[float]: ...


class FastReranker:
    """A cross-encoder through fastembed (ONNX), e.g. BAAI/bge-reranker-v2-m3-int8."""

    BATCH_SIZE = 8

    def __init__(self, model_id: str) -> None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder  # loads onnxruntime

        self.model_id = model_id
        self._model = TextCrossEncoder(model_id)

    def score(self, query: str, texts: list[str]) -> list[float]:
        return [float(score) for score in
                self._model.rerank(query, texts, batch_size=self.BATCH_SIZE)]


class FakeReranker:
    """Share of query words found in the text: deterministic and offline, for tests only."""

    model_id = "fake-overlap"

    def score(self, query: str, texts: list[str]) -> list[float]:
        words = set(tokens(query))
        return [len(words & set(tokens(text))) / max(len(words), 1) for text in texts]


def make_reranker(config: dict) -> Reranker:
    """Build the reranker named in config: {"provider": "fastembed" | "fake", "model": ...}."""
    if config["provider"] == "fake":
        return FakeReranker()
    if config["provider"] == "fastembed":
        return FastReranker(config["model"])
    raise ValueError(f"unknown reranker provider {config['provider']!r}")


def rerank(reranker: Reranker, corpus: Corpus, query: str,
           ranked: list[tuple[str, float]], depth: int) -> list[tuple[str, float]]:
    """Rescore the first `depth` candidates; the rest are dropped."""
    candidates = [chunk_id for chunk_id, _ in ranked[:depth]]
    if not candidates:
        return []
    scores = reranker.score(query, [corpus.chunks[chunk_id].text for chunk_id in candidates])
    return sorted(zip(candidates, scores, strict=True), key=lambda pair: -pair[1])
