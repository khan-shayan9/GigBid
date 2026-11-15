"""Okapi BM25 over chunk texts, for exact tool and library names that embeddings blur (V2)."""

import math
import re
from collections import Counter
from collections.abc import Collection

WORD = re.compile(r"[a-z0-9]+")
K1 = 1.5  # the usual Okapi defaults
B = 0.75


def tokens(text: str) -> list[str]:
    return WORD.findall(text.lower())


class BM25:
    def __init__(self, ids: list[str], texts: list[str]) -> None:
        self.ids = ids
        self.counts = [Counter(tokens(text)) for text in texts]
        self.lengths = [sum(counts.values()) for counts in self.counts]
        self.average_length = sum(self.lengths) / max(len(self.lengths), 1) or 1.0
        frequency = Counter(word for counts in self.counts for word in counts)
        total = len(texts)
        self.idf = {word: math.log(1 + (total - seen + 0.5) / (seen + 0.5))
                    for word, seen in frequency.items()}

    def search(self, query: str, allowed: Collection[str], depth: int) -> list[tuple[str, float]]:
        """The `depth` best chunk ids among `allowed`, best first; chunks sharing no word drop."""
        words = set(tokens(query)) & self.idf.keys()
        scored = []
        for chunk_id, counts, length in zip(self.ids, self.counts, self.lengths, strict=True):
            if chunk_id not in allowed:
                continue
            norm = K1 * (1 - B + B * length / self.average_length)
            score = sum(self.idf[word] * counts[word] * (K1 + 1) / (counts[word] + norm)
                        for word in words if word in counts)
            if score > 0:
                scored.append((chunk_id, score))
        return sorted(scored, key=lambda pair: -pair[1])[:depth]
