# source: synthetic · persona: ai_ml_engineer · repo: clinic-faq-bot
"""Split clinic leaflets into chunks and store their embeddings."""

import argparse
from pathlib import Path

from sentence_transformers import SentenceTransformer

CHUNK_TOKENS = 300
model = SentenceTransformer("all-MiniLM-L6-v2")


def chunk(text: str, size: int = CHUNK_TOKENS) -> list[str]:
    words = text.split()
    return [" ".join(words[i : i + size]) for i in range(0, len(words), size)]


def ingest(folder: Path, db) -> int:
    count = 0
    for leaflet in sorted(folder.glob("*.txt")):
        for piece in chunk(leaflet.read_text(encoding="utf-8")):
            vector = model.encode(piece).tolist()
            db.execute(
                "INSERT INTO chunks (leaflet, body, embedding) VALUES (%s, %s, %s)",
                (leaflet.stem, piece, vector),
            )
            count += 1
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args()
    print("call ingest(args.folder, db) with a psycopg connection")
