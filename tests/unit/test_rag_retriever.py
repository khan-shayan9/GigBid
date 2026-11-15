"""B2 variants through the retriever, offline: fake embedder, fake reranker, scripted model."""

from pathlib import Path

import pytest

from rag.index.bm25 import BM25
from rag.index.corpus import Corpus, load_corpus
from rag.index.embedder import FakeEmbedder
from rag.index.memory import MemoryIndex
from rag.retriever import Retriever
from rag.variants.v2_hybrid import rrf
from rag.variants.v3_rerank import FakeReranker

RAG = {"variant": "v0", "index": "memory", "chunk_words": 120, "chunk_overlap": 20,
       "candidates": 30, "rerank_depth": 20, "rrf_k": 60,
       "corrective": {"min_score": 0.5, "max_requeries": 1},
       "variants": {"v0": {}, "v1": {"decompose": True}, "v2": {"hybrid": True},
                    "v3": {"rerank": True}, "v8": {"rerank": True, "corrective": True}}}
CLINIC_BOT = "chatbot that answers patient questions from the clinic's leaflets"
EVIDENCE = lambda item: item.type in {"case_study", "cv", "repo", "review"}


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return load_corpus(Path("data/personas/ai_ml_engineer"), MemoryIndex(FakeEmbedder()), RAG)


def test_rrf_sums_reciprocal_ranks() -> None:
    fused = dict(rrf([["a", "b"], ["b", "c"]], k=60))
    assert fused["b"] == pytest.approx(1 / 62 + 1 / 61) and max(fused, key=fused.get) == "b"


def test_bm25_ranks_the_exact_term_first() -> None:
    bm25 = BM25(["a", "b", "c"], ["we used celery for queues", "plain prose", "celery celery"])
    hits = bm25.search("Celery workers", {"a", "b", "c"}, depth=5)
    assert [chunk_id for chunk_id, _ in hits] == ["c", "a"]
    assert bm25.search("celery", {"b"}, depth=5) == []


@pytest.mark.parametrize("variant", ["v0", "v2", "v3"])
def test_each_variant_finds_the_clinic_bot(corpus: Corpus, variant: str) -> None:
    retriever = Retriever(RAG, variant, reranker=FakeReranker())
    hits = retriever.search(corpus, CLINIC_BOT, 5, EVIDENCE)
    ids = [item.id for item, _ in hits]
    assert "ai-cs-01" in ids[:3] and len(ids) == len(set(ids)) <= 5
    assert all(EVIDENCE(item) for item, _ in hits)


def test_v1_retrieves_per_requirement_and_merges(corpus: Corpus) -> None:
    prompts: list[str] = []

    def complete(prompt: str) -> str:
        prompts.append(prompt)
        return f"- {CLINIC_BOT}\n2. scanned invoices totals column\n\n"

    retriever = Retriever(RAG, "v1", complete=complete, prompts={"decompose": "Post: {job_post}"})
    assert retriever.requirements("the post") == [CLINIC_BOT, "scanned invoices totals column"]
    ids = [item.id for item, _ in retriever.search_job(corpus, "the post", 4, EVIDENCE)]
    tops = {retriever.search(corpus, requirement, 1, EVIDENCE)[0][0].id
            for requirement in [CLINIC_BOT, "scanned invoices totals column"]}
    assert set(ids[:2]) == tops and prompts[0] == "Post: the post"  # each requirement's best


def test_v8_rewrites_once_then_refuses_when_nothing_is_strong(corpus: Corpus) -> None:
    rewrites: list[str] = []

    def complete(prompt: str) -> str:
        rewrites.append(prompt)
        return "zzz nothing matches this either"

    retriever = Retriever(RAG, "v8", reranker=FakeReranker(), complete=complete,
                          prompts={"rewrite": "Rewrite: {query}"})
    assert retriever.search(corpus, "quantum annealing hardware", 5, EVIDENCE) == []
    assert rewrites == ["Rewrite: quantum annealing hardware"]
    strong = retriever.search(corpus, "clinic leaflets", 5, EVIDENCE)
    assert strong and all(score >= 0.5 for _, score in strong) and len(rewrites) == 1


def test_variants_that_need_a_reranker_or_model_say_so(corpus: Corpus) -> None:
    with pytest.raises(ValueError, match="reranker"):
        Retriever(RAG, "v3").search(corpus, CLINIC_BOT, 5, EVIDENCE)
    with pytest.raises(ValueError, match="decompose"):
        Retriever(RAG, "v1").search_job(corpus, CLINIC_BOT, 5, EVIDENCE)
    # The tool path searches one requirement, so V1 works there without a model.
    assert Retriever(RAG, "v1").search(corpus, CLINIC_BOT, 5, EVIDENCE)
