"""Text embedders, chosen by `rag.embeddings` in agent/config.yaml."""

import hashlib
import re
from typing import Protocol

import numpy as np

FAKE_DIMENSIONS = 512
WORD = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    model_id: str

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


class FakeEmbedder:
    """Hashed bag of words: deterministic, offline, and shared words still score as similar."""

    model_id = "fake-bow"

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._embed(text) for text in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed(text)

    def _embed(self, text: str) -> np.ndarray:
        vector = np.zeros(FAKE_DIMENSIONS, dtype=np.float32)
        for word in WORD.findall(text.lower()):
            bucket = int.from_bytes(hashlib.md5(word.encode()).digest()[:4], "little")
            vector[bucket % FAKE_DIMENSIONS] += 1.0
        return _normalised(vector)


class FastEmbedder:
    """An open embedding model run locally on CPU through fastembed (ONNX)."""

    # nomic-embed-text was trained with these task prefixes; fastembed does not add them.
    DOCUMENT_PREFIX = "search_document: "
    QUERY_PREFIX = "search_query: "
    BATCH_SIZE = 8  # small batches keep memory low on a laptop CPU

    def __init__(self, model_id: str) -> None:
        from fastembed import TextEmbedding  # imported here so tests never load onnxruntime

        self.model_id = model_id
        self._model = TextEmbedding(model_id)

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        prefixed = [self.DOCUMENT_PREFIX + text for text in texts]
        vectors = np.stack(list(self._model.embed(prefixed, batch_size=self.BATCH_SIZE)))
        return np.stack([_normalised(vector) for vector in vectors])

    def embed_query(self, text: str) -> np.ndarray:
        return _normalised(next(iter(self._model.embed([self.QUERY_PREFIX + text]))))


def make_embedder(config: dict) -> Embedder:
    """Build the embedder named in config: {"provider": "fastembed" | "fake", "model": ...}."""
    if config["provider"] == "fake":
        return FakeEmbedder()
    if config["provider"] == "fastembed":
        return FastEmbedder(config["model"])
    raise ValueError(f"unknown embeddings provider {config['provider']!r}")


def _normalised(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    return (vector / norm if norm else vector).astype(np.float32)
