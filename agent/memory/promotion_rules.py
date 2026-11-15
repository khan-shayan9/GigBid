"""The only code that writes long-term memory (R7). Thresholds live in config `memory:`.

Style: a user's edit to a draft is counted under a coarse pattern (shorten, lengthen,
rephrase) and becomes a style memory once the same pattern repeats. Outcome: a GigSim
proposal event becomes an outcome memory from typed fields only, never raw tool output.
"""

from difflib import SequenceMatcher

from langgraph.store.base import BaseStore
from pydantic import BaseModel, Field

from agent.config import load_config
from agent.memory.store import OUTCOME, STYLE, STYLE_CANDIDATE
from data.pipeline.pii import mask_pii


class OutcomeMemory(BaseModel):
    job_id: str
    outcome: str
    skills: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


def _settings() -> dict:
    return load_config()["memory"]


def should_promote_style_edit(edit_count: int, consistent_pattern: bool) -> bool:
    # Conservative: one edit may be a one-off; only a repeated, consistent edit is a style.
    return edit_count >= _settings()["min_repeated_edits"] and consistent_pattern


def edit_pattern(draft: str, edited: str) -> str:
    """Coarse kind of edit; the key that must repeat before a style is learned."""
    change = _settings()["length_change_ratio"]
    if len(edited) < len(draft) * (1 - change):
        return "shorten"
    if len(edited) > len(draft) * (1 + change):
        return "lengthen"
    return "rephrase"


def _added_text(draft: str, edited: str) -> str:
    draft_words, edited_words = draft.split(), edited.split()
    opcodes = SequenceMatcher(None, draft_words, edited_words).get_opcodes()
    added = [edited_words[j1:j2] for tag, _, _, j1, j2 in opcodes if tag in ("insert", "replace")]
    return " ".join(word for chunk in added for word in chunk)


async def promote_style_edit(
    store: BaseStore, user_id: str, draft: str, edited: str, compliance_clean: bool
) -> dict | None:
    """Count one approved edit; return the style memory if this edit promoted it, else None."""
    settings = _settings()
    if not compliance_clean:
        return None
    if 1 - SequenceMatcher(None, draft, edited).ratio() < settings["min_edit_ratio"]:
        return None
    added = _added_text(draft, edited)
    if mask_pii(added) != added:  # reject, don't mask: a contact detail is never a style
        return None

    pattern = edit_pattern(draft, edited)
    counter = await store.aget((STYLE_CANDIDATE, user_id), pattern)
    count = (counter.value["count"] if counter else 0) + 1
    await store.aput((STYLE_CANDIDATE, user_id), pattern, {"count": count})
    if not should_promote_style_edit(count, consistent_pattern=True):
        return None
    memory = {"pattern": pattern, "edit_count": count,
              "example": added[: settings["max_example_chars"]]}
    await store.aput((STYLE, user_id), pattern, memory)
    return memory


async def promote_outcome(
    store: BaseStore, user_id: str, job_id: str, event: str,
    skills: list[str], evidence_ids: list[str],
) -> OutcomeMemory | None:
    """Record a proposal outcome; a later event for the same job overwrites the earlier one."""
    if event not in _settings()["outcome_events"]:
        return None
    memory = OutcomeMemory(job_id=job_id, outcome=event, skills=skills,
                           evidence_ids=evidence_ids)
    await store.aput((OUTCOME, user_id), job_id, memory.model_dump())
    return memory
