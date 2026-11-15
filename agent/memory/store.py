"""Read and delete access to long-term memory (C2, R7).

Writes live only in `agent/memory/promotion_rules.py`; this module has no public put.
"""

from langgraph.store.base import BaseStore

STYLE = "style"
OUTCOME = "outcome"
STYLE_CANDIDATE = "style_candidate"  # pre-promotion edit counters; not learned memory
MEMORY_KINDS = (STYLE, OUTCOME)
LIST_LIMIT = 1000  # BaseStore.search defaults to 10, which would silently truncate the viewer


async def list_memories(store: BaseStore, kind: str, user_id: str) -> list[dict]:
    """Return one user's promoted items of one kind, for the memory viewer."""
    if kind not in MEMORY_KINDS:
        raise ValueError(f"unknown memory kind: {kind}")
    items = await store.asearch((kind, user_id), limit=LIST_LIMIT)
    return [{"id": item.key, **item.value} for item in items]


async def delete_memory(store: BaseStore, kind: str, user_id: str, item_id: str) -> None:
    """Delete one promoted item. A deleted style item also loses its counter, so it stays gone."""
    if kind not in MEMORY_KINDS:
        raise ValueError(f"unknown memory kind: {kind}")
    await store.adelete((kind, user_id), item_id)
    if kind == STYLE:
        await store.adelete((STYLE_CANDIDATE, user_id), item_id)
