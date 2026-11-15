"""Portfolio MCP tools: search_evidence, get_case_study, list_skills (all read-only)."""

import asyncio
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from mcp_servers.portfolio.store import PortfolioStore
from rag.ingest.portfolio import EvidenceItem, EvidenceType, Outcome, cv_skills

MAX_TEXT_CHARS = 2000  # keeps one search result within a node's token budget
READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
EvidenceId = Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_-]+$")]


class EvidenceFilters(BaseModel):
    # Past proposals paraphrase the case studies and outnumber them, so they are opt-in.
    types: list[EvidenceType] = Field(
        default=["case_study", "cv", "repo", "review"], min_length=1,
        description="Evidence types to search. Add 'proposal' for past proposals, which show "
                    "what was pitched, not what was done.")
    outcomes: list[Outcome] = Field(default=[], description="Past proposals with these outcomes")


class EvidenceHit(EvidenceItem):
    score: float = Field(description="Relevance to the requirement under the active retrieval "
                                     "variant; higher is better (cosine, fused rank or "
                                     "reranker score)")


class EvidenceResults(BaseModel):
    items: list[EvidenceHit]


class Skills(BaseModel):
    skills: list[str]
    not_offered: str = Field(description="Work the freelancer says they do not take")


def register_tools(mcp: FastMCP, store: PortfolioStore) -> None:
    @mcp.tool(annotations=READ)
    async def search_evidence(
        requirement: Annotated[str, Field(min_length=1, max_length=500)],
        k: Annotated[int, Field(ge=1, le=20)] = 5,
        filters: EvidenceFilters | None = None,
    ) -> EvidenceResults:
        """Find portfolio evidence for one job requirement, best match first. Cite `id`."""
        filters = filters or EvidenceFilters()
        corpus = await store.corpus()
        hits = await asyncio.to_thread(
            store.retriever.search, corpus, requirement, k,
            lambda item: item.type in filters.types
            and (not filters.outcomes or item.outcome in filters.outcomes))
        return EvidenceResults(items=[
            EvidenceHit(**item.model_dump() | {"text": item.text[:MAX_TEXT_CHARS]}, score=score)
            for item, score in hits])

    @mcp.tool(annotations=READ)
    async def get_case_study(case_id: EvidenceId) -> EvidenceItem:
        """Get one case study in full."""
        item = await store.find(case_id, "case_study")
        if not item:
            raise ToolError(f"case_study_not_found: {case_id}")
        return item

    @mcp.tool(annotations=READ)
    async def list_skills() -> Skills:
        """List the skills on the freelancer's CV and the work they do not take."""
        skills, not_offered = await asyncio.to_thread(cv_skills, store.user_dir())
        return Skills(skills=skills, not_offered=not_offered)
