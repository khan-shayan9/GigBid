"""Chunk vectors in Postgres with pgvector (ADR 0001): the index docker compose and CI use.

Rows are keyed by persona (the tenant), embedding model and chunk id, so two models never mix
and one persona never sees another's evidence. Each row keeps the chunk's item metadata.

shortcut: exact search with no ANN index; three portfolios of a few hundred chunks need none.
Add an HNSW index (with a fixed vector dimension) if a corpus grows past ~100k chunks.
"""

import json
from collections.abc import Collection

import numpy as np
import psycopg

from rag.index.embedder import Embedder
from rag.index.memory import content_hash, sync_report
from rag.ingest.chunking import Chunk

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS evidence_chunks (
    persona text NOT NULL,
    model text NOT NULL,
    id text NOT NULL,
    item_id text NOT NULL,
    content_hash text NOT NULL,
    metadata jsonb NOT NULL,
    embedding vector NOT NULL,
    PRIMARY KEY (persona, model, id)
);
"""


def _literal(vector: np.ndarray) -> str:
    return "[" + ",".join(f"{value:.7g}" for value in vector) + "]"


class PgVectorIndex:
    def __init__(self, embedder: Embedder, database_url: str) -> None:
        self.embedder = embedder
        self.embedded = 0
        # psycopg takes a plain postgresql:// URL, not SQLAlchemy's postgresql+psycopg://.
        self._db = psycopg.connect(database_url.replace("+psycopg", ""), autocommit=True)
        self._db.execute(SCHEMA)

    def sync(self, persona: str, chunks: list[Chunk],
             metadata: dict[str, dict] | None = None) -> dict[str, int]:
        """Make the persona's rows match `chunks`, embedding only new or changed text."""
        rows = self._db.execute(
            "SELECT id, content_hash FROM evidence_chunks WHERE persona = %s AND model = %s",
            (persona, self.embedder.model_id)).fetchall()
        old = dict(rows)
        new = {chunk.id: content_hash(chunk.text) for chunk in chunks}
        changed = [chunk for chunk in chunks if old.get(chunk.id) != new[chunk.id]]
        if changed:
            self.embedded += len(changed)
            vectors = self.embedder.embed_documents([chunk.text for chunk in changed])
            with self._db.transaction():
                for chunk, vector in zip(changed, vectors, strict=True):
                    self._db.execute(
                        "INSERT INTO evidence_chunks VALUES (%s, %s, %s, %s, %s, %s, %s::vector) "
                        "ON CONFLICT (persona, model, id) DO UPDATE SET "
                        "content_hash = EXCLUDED.content_hash, metadata = EXCLUDED.metadata, "
                        "embedding = EXCLUDED.embedding",
                        (persona, self.embedder.model_id, chunk.id, chunk.item_id,
                         new[chunk.id], json.dumps((metadata or {}).get(chunk.item_id, {})),
                         _literal(vector)))
        removed = list(old.keys() - new.keys())
        if removed:
            self._db.execute(
                "DELETE FROM evidence_chunks WHERE persona = %s AND model = %s AND id = ANY(%s)",
                (persona, self.embedder.model_id, removed))
        return sync_report(old, new)

    def search(self, persona: str, query: np.ndarray, k: int,
               chunk_ids: Collection[str]) -> list[tuple[str, float]]:
        """The k chunks among `chunk_ids` most similar to the query, best first (cosine)."""
        rows = self._db.execute(
            "SELECT id, 1 - (embedding <=> %(q)s::vector) FROM evidence_chunks "
            "WHERE persona = %(persona)s AND model = %(model)s AND id = ANY(%(ids)s) "
            "ORDER BY embedding <=> %(q)s::vector, id LIMIT %(k)s",
            {"q": _literal(query), "persona": persona, "model": self.embedder.model_id,
             "ids": list(chunk_ids), "k": k}).fetchall()
        return [(chunk_id, float(score)) for chunk_id, score in rows]
