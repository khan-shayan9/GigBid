"""Proposal Writer: draft a cover letter in which every experience claim cites portfolio evidence.

Evidence comes only from the Portfolio MCP tool `search_evidence`; a sentence citing an id that
search did not return is removed before the draft leaves this node.
"""

import re
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from agent.config import load_policy, load_prompt
from agent.handoffs import ProposalDraft
from agent.mcp_client import McpClient
from agent.state import GigBidState

NODE = "writer"
EVIDENCE_PER_REQUIREMENT = 3
MAX_REQUIREMENTS = 6
EVIDENCE_CHARS = 600  # enough of each item to ground a claim, small enough for the token budget
MAX_WORDS = 180
CITATION = re.compile(r"\[([A-Za-z0-9_-]+)\]")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def requirements(job: dict[str, Any]) -> list[str]:
    """What to search evidence for.

    shortcut: the post's title and listed skills; the Job Analyst's JobSpec replaces this in
    Phase 5.
    """
    return [job["title"], *job.get("skills", [])][:MAX_REQUIREMENTS]


async def gather_evidence(job: dict[str, Any], mcp: McpClient) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    for requirement in requirements(job):
        result = await mcp.call(NODE, "search_evidence",
                                {"requirement": requirement, "k": EVIDENCE_PER_REQUIREMENT})
        for item in result["items"]:
            evidence.setdefault(item["id"], item)
    return evidence


def keep_grounded(letter: str, known_ids: set[str]) -> tuple[str, list[str]]:
    """Drop sentences that cite an id outside `known_ids`; return the letter and cited ids."""
    kept, cited = [], []
    for paragraph in letter.strip().split("\n\n"):
        sentences = [sentence for sentence in SENTENCE_END.split(paragraph.strip())
                     if set(CITATION.findall(sentence)) <= known_ids]
        kept.append(" ".join(sentences))
        cited += [id_ for sentence in sentences for id_ in CITATION.findall(sentence)]
    return "\n\n".join(part for part in kept if part), list(dict.fromkeys(cited))


async def draft_proposal(job: dict[str, Any], mcp: McpClient, model: BaseChatModel,
                         feedback: str = "") -> tuple[ProposalDraft, list[dict[str, Any]]]:
    return await write_letter(job, await gather_evidence(job, mcp), model, feedback)


def _listing(evidence: dict[str, dict[str, Any]]) -> str:
    return "\n\n".join(f"[{item['id']}] ({item['type']}) {item['title']}\n"
                       f"{item['text'][:EVIDENCE_CHARS]}" for item in evidence.values())


def _post(job: dict[str, Any]) -> str:
    # Strip the closing tag so the post cannot break out of its delimiters.
    return f"{job['title']}\n\n{job['description']}".replace("</job_post>", "")


async def rewrite_paragraph(job: dict[str, Any], evidence: dict[str, dict[str, Any]],
                            paragraph: str, model: BaseChatModel) -> str:
    """Proposal studio's "regenerate": one paragraph, grounded in the draft's evidence.

    Lines carrying a phrase the policy requires (the AI-assistance disclosure) are kept as they
    are: the model is not asked to rewrite them, so it cannot drop them."""
    required = [phrase.lower() for rule in load_policy().get("required", [])
                if "proposal" in rule["applies_to"] for phrase in rule["any_of"]]
    lines = paragraph.splitlines()
    kept = [line for line in lines if any(phrase in line.lower() for phrase in required)]
    body = "\n".join(line for line in lines if line not in kept)
    if not body.strip():
        return paragraph
    prompt = load_prompt("writer_paragraph").format(job_post=_post(job),
                                                    evidence=_listing(evidence),
                                                    paragraph=body)
    reply = await model.ainvoke([HumanMessage(prompt)])
    return "\n".join([keep_grounded(str(reply.content), set(evidence))[0], *kept])


async def write_letter(job: dict[str, Any], evidence: dict[str, dict[str, Any]],
                       model: BaseChatModel,
                       feedback: str = "") -> tuple[ProposalDraft, list[dict[str, Any]]]:
    """Draft from evidence already gathered (by id); evaluation runs pass each variant's."""
    prompt = load_prompt(NODE).format(max_words=MAX_WORDS, job_post=_post(job),
                                     evidence=_listing(evidence), feedback=feedback or "(none)")
    reply = await model.ainvoke([HumanMessage(prompt)])
    letter, cited = keep_grounded(str(reply.content), set(evidence))
    draft = ProposalDraft(job_id=job["job_id"], cover_letter=letter, evidence_ids=cited)
    return draft, [evidence[id_] for id_ in cited]


async def writer(state: GigBidState, config: RunnableConfig) -> GigBidState:
    """Graph node. `config["configurable"]` carries the run's `mcp` client and `model`."""
    options = config["configurable"]
    feedback = "\n".join(state.get("critique", {}).get("reasons", []))
    draft, evidence = await draft_proposal(state["job"], options["mcp"], options["model"],
                                           feedback)
    return {"proposal_draft": draft.model_dump(), "evidence": evidence}
