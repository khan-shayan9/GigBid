"""B1 ingestion: item metadata, fixed chunks, PDF CVs, GitHub files and incremental re-indexing."""

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from rag.index.corpus import load_corpus
from rag.index.embedder import FakeEmbedder
from rag.index.memory import MemoryIndex
from rag.ingest.chunking import chunk_items
from rag.ingest.github import fetch_github_repo
from rag.ingest.portfolio import EvidenceItem, load_portfolio

PERSONAS = Path("data/personas")
RAG = {"chunk_words": 120, "chunk_overlap": 20}


def test_every_item_carries_its_metadata() -> None:
    items = {item.id: item for item in load_portfolio(PERSONAS / "ai_ml_engineer")}
    assert all(item.persona == "ai_ml_engineer" for item in items.values())
    case = items["ai-cs-01"]
    assert case.project == "ai-cs-01" and case.client_industry == "a three-site physiotherapy clinic"
    review = items["ai-rev-01"]
    assert review.project == "ai-cs-01" and review.client_industry == case.client_industry
    proposal = items["ai_ml_engineer-prop-001"]
    assert proposal.outcome and proposal.project and proposal.date
    assert "Python" in items["ai-cs-02"].skills


def test_chunks_are_fixed_overlapping_windows_with_item_ids() -> None:
    item = EvidenceItem(id="x", type="cv", title="t", source="s",
                        text=" ".join(f"w{n}" for n in range(250)))
    chunks = chunk_items([item], words=100, overlap=20)
    assert [chunk.id for chunk in chunks] == ["x#0", "x#1", "x#2"]
    assert chunks[1].text.split()[0] == "w80" and all(chunk.item_id == "x" for chunk in chunks)
    short = item.model_copy(update={"text": "only a few words"})
    assert [chunk.text for chunk in chunk_items([short], 100, 20)] == ["only a few words"]
    with pytest.raises(ValueError):
        chunk_items([item], words=10, overlap=10)


def _pdf(text: str) -> bytes:
    """A one-page PDF with one line of Helvetica text, built by hand (no PDF writer needed)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
               b"/Resources << /Font << /F1 5 0 R >> >> >>"),
               b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, xref)


def _persona(tmp_path: Path) -> Path:
    persona = tmp_path / "pdf_user"
    shutil.copytree(PERSONAS / "ai_ml_engineer", persona, ignore=shutil.ignore_patterns("cv.md"))
    return persona


def test_a_pdf_cv_is_loaded_as_cv_evidence(tmp_path: Path) -> None:
    persona = _persona(tmp_path)
    (persona / "cv.pdf").write_bytes(_pdf("Seven years of Kubernetes and Terraform work"))
    cvs = [item for item in load_portfolio(persona) if item.type == "cv"]
    assert [cv.id for cv in cvs] == ["pdf_user-cv-pdf"]
    assert "Kubernetes and Terraform" in cvs[0].text


def test_reindexing_embeds_only_new_or_changed_chunks(tmp_path: Path) -> None:
    persona = _persona(tmp_path)
    shutil.copy(PERSONAS / "ai_ml_engineer" / "cv.md", persona / "cv.md")
    index = MemoryIndex(FakeEmbedder())
    first = load_corpus(persona, index, RAG)
    distinct_texts = len({chunk.text for chunk in first.chunks.values()})  # same text, one vector
    assert first.last_sync["added"] == len(first.chunks) and index.embedded == distinct_texts

    again = load_corpus(persona, index, RAG)
    assert again.last_sync == {"added": 0, "updated": 0, "removed": 0,
                               "unchanged": len(first.chunks)}
    assert index.embedded == distinct_texts

    reviews = persona / "reviews.jsonl"
    rows = [json.loads(line) for line in reviews.read_text(encoding="utf-8").splitlines()]
    rows[0]["text"] = "Rewritten review text about a brand new project."
    reviews.write_text("\n".join(json.dumps(row) for row in rows[:-1]), encoding="utf-8")
    edited = load_corpus(persona, index, RAG)
    assert edited.last_sync["updated"] == 1 and edited.last_sync["removed"] == 1
    assert edited.last_sync["added"] == 0 and index.embedded == distinct_texts + 1


async def test_github_files_land_in_the_portfolio_folder(tmp_path: Path) -> None:
    listing = [{"name": "README.md", "type": "file"}, {"name": "app.py", "type": "file"},
               {"name": "logo.png", "type": "file"}, {"name": "src", "type": "dir"},
               {"name": "../escape.md", "type": "file"}]
    calls: list[dict[str, Any]] = []

    async def call_tool(tool: str, args: dict[str, Any]) -> dict[str, Any]:
        calls.append(args)
        if args["path"] == "/":
            return {"content": ["listing follows", json.dumps(listing)]}
        return {"content": ["ok", f"contents of {args['path']}"]}

    written = await fetch_github_repo("octo", "demo-repo", tmp_path, call_tool)
    assert sorted(path.name for path in written) == ["README.md", "app.py"]
    assert (tmp_path / "repos" / "demo-repo" / "app.py").read_text() == "contents of app.py"
    assert all(".." not in call["path"] for call in calls)
    with pytest.raises(ValueError):
        await fetch_github_repo("octo", "../etc", tmp_path, call_tool)
