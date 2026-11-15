"""Cut evidence items into fixed-size, overlapping word windows: the chunks the index stores."""

from pydantic import BaseModel

from rag.ingest.portfolio import EvidenceItem


class Chunk(BaseModel):
    id: str  # "<item id>#<n>"; search results are reported per item, so item ids stay citable
    item_id: str
    text: str


def chunk_items(items: list[EvidenceItem], words: int, overlap: int) -> list[Chunk]:
    if not 0 <= overlap < words:
        raise ValueError("chunk overlap must be at least 0 and smaller than the chunk size")
    chunks = []
    for item in items:
        tokens = item.text.split()
        starts = range(0, max(len(tokens) - overlap, 1), words - overlap)
        chunks += [Chunk(id=f"{item.id}#{number}", item_id=item.id,
                         text=" ".join(tokens[start:start + words]))
                   for number, start in enumerate(starts)]
    return chunks
