"""Shared helpers for the Part B runners: datasets, corpora, cached model calls, percentiles.

Model replies are cached in data/processed/eval_cache/<name>.jsonl by (model, prompt), so a run
stopped by Groq's free-tier rate limit (8,000 tokens a minute) resumes where it left off, and a
rerun of the table costs no tokens. Delete a cache file when its prompt or model changes.
"""

import hashlib
import json
import math
import threading
import time
from pathlib import Path
from typing import Any

from openai import RateLimitError

from agent.config import load_config
from agent.llm import chat_model
from mcp_servers.common import REPO_ROOT
from rag.index.corpus import Corpus, load_corpus
from rag.index.embedder import make_embedder
from rag.index.memory import MemoryIndex
from rag.variants.v3_rerank import Reranker, make_reranker

DATASETS = REPO_ROOT / "evals" / "datasets"
RESULTS = REPO_ROOT / "evals" / "results"
SEED = REPO_ROOT / "data" / "gigsim_seed"
PERSONAS = REPO_ROOT / "data" / "personas"
CACHE = REPO_ROOT / "data" / "processed" / "eval_cache"
EMBEDDING_CACHE = REPO_ROOT / "data" / "processed" / "embeddings"
PERSONA_DOMAIN = {"ai_ml_engineer": "ai_ml", "fullstack_dev": "web", "data_analyst": "data"}
MAX_RETRIES = 10  # the client waits and retries on Groq's 429s
RATE_LIMIT_WAITS = 30
RATE_LIMIT_SLEEP_S = 15


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def labels(split: str) -> list[dict[str, Any]]:
    return jsonl(DATASETS / f"{split}.jsonl")


def jobs() -> dict[str, dict[str, Any]]:
    return {job["job_id"]: job for job in jsonl(SEED / "jobs.jsonl")}


def annotations() -> dict[str, dict[str, Any]]:
    return {row["job_id"]: row for row in jsonl(DATASETS / "job_annotations.jsonl")}


def job_post(job: dict[str, Any]) -> str:
    """What a freelancer sees: title, description and listed skills."""
    return f"{job['title']}\n\n{job['description']}\n\nSkills: {', '.join(job['skills'])}"


def corpora(rag_config: dict) -> dict[str, Corpus]:
    """Every persona's corpus on the in-memory index with the configured embedder."""
    index = MemoryIndex(make_embedder(load_config()["models"]["embeddings"]), EMBEDDING_CACHE)
    return {persona: load_corpus(PERSONAS / persona, index, rag_config)
            for persona in PERSONA_DOMAIN}


def percentile(values: list[float], share: float) -> float | None:
    """Nearest-rank percentile; None when there are no values."""
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(math.ceil(share * len(ordered)) - 1, 0)], 4)


class CachedModel:
    """A node's chat model as a sync `prompt -> reply` function, cached on disk with usage."""

    def __init__(self, node: str, name: str, **overrides: Any) -> None:
        self.model = chat_model(node, max_retries=MAX_RETRIES, **overrides)
        self.path = CACHE / f"{name}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.rows = {row["key"]: row for row in jsonl(self.path)} if self.path.exists() else {}
        self.log: list[dict[str, Any]] = []  # every call this run, cached or not, for cost
        self._lock = threading.Lock()

    def __call__(self, prompt: str) -> str:
        return self.call(prompt)["reply"]

    def call(self, prompt: str) -> dict[str, Any]:
        """{"reply", "input_tokens", "output_tokens", "seconds"}; from the cache when possible."""
        key = hashlib.sha256(f"{self.model.model_name}\n{prompt}".encode()).hexdigest()
        if key not in self.rows:
            started = time.perf_counter()
            message = self._invoke(prompt)
            usage = message.usage_metadata or {}
            row = {"key": key, "model": self.model.model_name, "reply": str(message.content),
                   "input_tokens": usage.get("input_tokens", 0),
                   "output_tokens": usage.get("output_tokens", 0),
                   "seconds": round(time.perf_counter() - started, 3)}
            with self._lock, self.path.open("a", encoding="utf-8") as cache:
                cache.write(json.dumps(row) + "\n")
            self.rows[key] = row
        self.log.append(self.rows[key])
        return self.rows[key]

    def _invoke(self, prompt: str) -> Any:
        # Runs share a model's tokens-per-minute budget; the client's own retries can run out.
        for _ in range(RATE_LIMIT_WAITS):
            try:
                return self.model.invoke(prompt)
            except RateLimitError:
                time.sleep(RATE_LIMIT_SLEEP_S)
        return self.model.invoke(prompt)


class CachedReranker:
    """The configured reranker with its scores cached on disk by (model, query, text)."""

    def __init__(self) -> None:
        self._reranker: Reranker | None = None
        self.model_id = load_config()["models"]["reranker"]["model"]
        self.path = CACHE / f"rerank-{self.model_id.replace('/', '_')}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.scores = {row["key"]: row["score"] for row in jsonl(self.path)} \
            if self.path.exists() else {}

    def score(self, query: str, texts: list[str]) -> list[float]:
        keys = [hashlib.sha256(f"{query}\n{text}".encode()).hexdigest() for text in texts]
        missing = [(key, text) for key, text in zip(keys, texts, strict=True)
                   if key not in self.scores]
        if missing:
            self._reranker = self._reranker or make_reranker(load_config()["models"]["reranker"])
            fresh = self._reranker.score(query, [text for _, text in missing])
            with self.path.open("a", encoding="utf-8") as cache:
                for (key, _), value in zip(missing, fresh, strict=True):
                    self.scores[key] = value
                    cache.write(json.dumps({"key": key, "score": value}) + "\n")
        return [self.scores[key] for key in keys]
