"""The pgvector index against a real Postgres (CI service container; skipped without one)."""

import os
import uuid
from pathlib import Path

import pytest

from rag.index.corpus import load_corpus
from rag.index.embedder import FakeEmbedder
from rag.index.memory import MemoryIndex

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"),
                                reason="needs Postgres with pgvector (DATABASE_URL)")
RAG = {"chunk_words": 120, "chunk_overlap": 20}
PERSONA = Path("data/personas/data_analyst")


def test_pgvector_matches_memory_and_syncs_incrementally() -> None:
    from rag.index.pgvector import PgVectorIndex

    embedder = FakeEmbedder()
    embedder.model_id = f"fake-{uuid.uuid4().hex[:8]}"  # a fresh namespace per test run
    pg = PgVectorIndex(embedder, os.environ["DATABASE_URL"])
    corpus = load_corpus(PERSONA, pg, RAG)
    assert corpus.last_sync["added"] == len(corpus.chunks)
    assert load_corpus(PERSONA, pg, RAG).last_sync["unchanged"] == len(corpus.chunks)
    assert pg.embedded == len(corpus.chunks)

    memory = MemoryIndex(embedder)
    load_corpus(PERSONA, memory, RAG)
    query = embedder.embed_query("dashboard for monthly sales in Power BI")
    ids = set(corpus.chunks)
    # Scores, not ids: bag-of-words vectors tie, and float32 vs the text literal may reorder ties.
    pg_scores = [score for _, score in pg.search(PERSONA.name, query, 5, ids)]
    memory_scores = [score for _, score in memory.search(PERSONA.name, query, 5, ids)]
    assert pg_scores == pytest.approx(memory_scores, abs=1e-5)
    assert pg.search("someone_else", query, 5, ids) == []  # rows are scoped by persona
