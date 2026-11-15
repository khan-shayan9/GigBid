from langgraph.store.memory import InMemoryStore

from agent.memory.promotion_rules import promote_outcome, promote_style_edit
from agent.memory.store import OUTCOME, STYLE, delete_memory, list_memories

DRAFT = ("Hello, I am a seasoned engineer with many years of experience building data "
         "pipelines and dashboards for clients across many industries and I would love to help.")
SHORT = "I built data pipelines and dashboards for clients. I would love to help."


async def shorten_times(store: InMemoryStore, times: int) -> list:
    return [await promote_style_edit(store, "u1", DRAFT, SHORT, compliance_clean=True)
            for _ in range(times)]


async def test_repeated_edit_promotes_style() -> None:
    store = InMemoryStore()
    results = await shorten_times(store, 3)
    assert results[:2] == [None, None]
    assert results[2]["pattern"] == "shorten"
    assert [m["id"] for m in await list_memories(store, STYLE, "u1")] == ["shorten"]
    assert await list_memories(store, STYLE, "u2") == []


async def test_rejected_edits_never_promote() -> None:
    store = InMemoryStore()
    tiny = DRAFT.replace("Hello", "Hi")
    with_email = SHORT + " Email me at jo@example.com"
    for _ in range(5):
        assert await promote_style_edit(store, "u1", DRAFT, tiny, True) is None
        assert await promote_style_edit(store, "u1", DRAFT, with_email, True) is None
        assert await promote_style_edit(store, "u1", DRAFT, SHORT, False) is None
    assert await list_memories(store, STYLE, "u1") == []


async def test_outcome_promotion_keeps_latest_event_only_for_known_events() -> None:
    store = InMemoryStore()
    await promote_outcome(store, "u1", "job-1", "replied", ["python"], ["cs-1"])
    await promote_outcome(store, "u1", "job-1", "hired", ["python"], ["cs-1"])
    assert await promote_outcome(store, "u1", "job-2", "viewed", ["sql"], []) is None
    memories = await list_memories(store, OUTCOME, "u1")
    assert memories == [{"id": "job-1", "job_id": "job-1", "outcome": "hired",
                         "skills": ["python"], "evidence_ids": ["cs-1"]}]


async def test_delete_removes_item_and_its_counter() -> None:
    store = InMemoryStore()
    await shorten_times(store, 3)
    await delete_memory(store, STYLE, "u1", "shorten")
    assert await list_memories(store, STYLE, "u1") == []
    assert await shorten_times(store, 1) == [None]  # counting starts over after delete
