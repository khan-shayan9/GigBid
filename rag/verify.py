"""B3 claim verification: split a draft into claims and grade each against the evidence.

A model reads the numbered sentences and the evidence, lists each claim about the freelancer's
experience, skills or results, and labels it supported, partly supported or unsupported.
Sentences holding an unsupported claim are removed before the Critic sees the draft.
The model call and the prompt are passed in, so this module never touches a database, names a
model or holds a prompt; graph nodes may import it (2.ARCHITECTURE.md §10).
"""

import json
import re
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, TypeAdapter, ValidationError

from rag.variants.v1_decompose import visible

Label = Literal["supported", "partly_supported", "unsupported"]
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
EVIDENCE_CHARS = 600  # the same budget the writer used, so both see the same text


class ClaimVerdict(BaseModel):
    sentence: int  # 0-based index into split_sentences(draft)
    claim: str
    label: Label
    evidence_ids: list[str] = []
    reason: str = ""


VERDICTS = TypeAdapter(list[ClaimVerdict])


class VerificationFailed(ValueError):
    """The model's reply was not a usable list of verdicts."""


def split_sentences(draft: str) -> list[str]:
    return [sentence for paragraph in draft.strip().split("\n\n")
            for sentence in SENTENCE_END.split(paragraph.strip()) if sentence]


def verify_claims(draft: str, evidence: list[dict[str, Any]], complete: Callable[[str], str],
                  prompt: str) -> list[ClaimVerdict]:
    """One verdict per claim the model finds; sentences with no claim get none."""
    sentences = split_sentences(draft)
    numbered = "\n".join(f"{number}. {sentence}" for number, sentence in enumerate(sentences))
    listing = "\n\n".join(f"[{item['id']}] {item['title']}\n{item['text'][:EVIDENCE_CHARS]}"
                          for item in evidence) or "(no evidence)"
    reply = visible(complete(prompt.format(sentences=numbered, evidence=listing)))
    start, end = reply.find("["), reply.rfind("]")
    try:
        verdicts = VERDICTS.validate_python(json.loads(reply[start:end + 1]))
    except (ValueError, ValidationError) as error:
        raise VerificationFailed(f"unparseable verdicts: {reply[:200]!r}") from error
    return [verdict for verdict in verdicts if 0 <= verdict.sentence < len(sentences)]


def remove_unsupported(draft: str, verdicts: list[ClaimVerdict]) -> str:
    """The draft without every sentence that holds an unsupported claim; paragraphs kept."""
    dropped = {verdict.sentence for verdict in verdicts if verdict.label == "unsupported"}
    paragraphs, number = [], 0
    for paragraph in draft.strip().split("\n\n"):
        kept = []
        for sentence in SENTENCE_END.split(paragraph.strip()):
            if not sentence:
                continue
            if number not in dropped:
                kept.append(sentence)
            number += 1
        paragraphs.append(" ".join(kept))
    return "\n\n".join(part for part in paragraphs if part)


def count_labels(verdicts: list[ClaimVerdict]) -> dict[str, int]:
    return {label: sum(verdict.label == label for verdict in verdicts)
            for label in ("supported", "partly_supported", "unsupported")}
