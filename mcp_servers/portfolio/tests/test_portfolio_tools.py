"""Portfolio MCP tools, resources and prompts through an in-memory MCP client (fake embedder)."""

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from mcp import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session
from pydantic import AnyUrl

from mcp_servers.portfolio.server import create_server, embeddings_config
from mcp_servers.portfolio.store import PortfolioSettings
from rag.index.embedder import FakeEmbedder, make_embedder

CLINIC_BOT = "chatbot that answers patient questions from the clinic's leaflets"


@asynccontextmanager
async def open_session(user: str | None, embedder: Any = None) -> AsyncIterator[ClientSession]:
    settings = PortfolioSettings(stdio_user=user, cache_dir=None)
    server = create_server(settings, embedder or FakeEmbedder())
    async with create_connected_server_and_client_session(server) as session:
        yield session


async def call(session: ClientSession, tool: str, **args: Any) -> dict[str, Any]:
    result = await session.call_tool(tool, args)
    assert not result.isError, result.content
    return result.structuredContent


async def error_of(session: ClientSession, tool: str, **args: Any) -> str:
    result = await session.call_tool(tool, args)
    assert result.isError
    return result.content[0].text.removeprefix(f"Error executing tool {tool}: ")


async def test_search_evidence_finds_the_matching_case_study() -> None:
    async with open_session("ai_ml_engineer") as session:
        result = await call(session, "search_evidence", requirement=CLINIC_BOT, k=3,
                            filters={"types": ["case_study"]})
    top = result["items"][0]
    assert top["id"] == "ai-cs-01" and top["type"] == "case_study"
    assert top["source"] == "case_studies.md#ai-cs-01" and top["date"] == "2024"
    assert [item["score"] for item in result["items"]] == sorted(
        (item["score"] for item in result["items"]), reverse=True)


async def test_default_search_leaves_out_past_proposals_and_refusals() -> None:
    async with open_session("fullstack_dev") as session:
        result = await call(session, "search_evidence", requirement="mobile apps", k=20)
    assert {item["type"] for item in result["items"]} <= {"case_study", "cv", "repo", "review"}
    assert not any(item["id"].endswith("not-my-thing") for item in result["items"])


async def test_filters_return_past_proposals_with_outcomes() -> None:
    async with open_session("ai_ml_engineer") as session:
        result = await call(session, "search_evidence", requirement=CLINIC_BOT, k=10,
                            filters={"types": ["proposal"], "outcomes": ["won"]})
    assert result["items"]
    assert all(item["type"] == "proposal" and item["outcome"] == "won" and item["date"]
               for item in result["items"])


async def test_each_user_sees_only_their_own_portfolio() -> None:
    async with open_session("data_analyst") as session:
        result = await call(session, "search_evidence", requirement=CLINIC_BOT, k=20)
        assert not any(item["id"].startswith("ai") for item in result["items"])
        assert (await error_of(session, "get_case_study", case_id="ai-cs-01")).startswith(
            "case_study_not_found")
        with pytest.raises(Exception, match="case_study_not_found"):
            await session.read_resource(AnyUrl("portfolio://case/ai-cs-01"))
    async with open_session("ai_ml_engineer") as session:
        assert (await call(session, "get_case_study", case_id="ai-cs-01"))["title"]


async def test_unknown_or_missing_user_is_refused() -> None:
    for user in (None, "../ai_ml_engineer", "nobody"):
        async with open_session(user) as session:
            assert (await error_of(session, "list_skills")).startswith("unauthenticated")


async def test_list_skills_reads_the_cv() -> None:
    async with open_session("fullstack_dev") as session:
        skills = await call(session, "list_skills")
    assert "Next.js (App Router)" in skills["skills"] and "TypeScript" in skills["skills"]
    assert "blockchain" in skills["not_offered"]


async def test_resources_and_prompts() -> None:
    async with open_session("ai_ml_engineer") as session:
        case = await session.read_resource(AnyUrl("portfolio://case/ai-cs-01"))
        assert case.contents[0].text.startswith("# MedAssist")
        proposal = await session.read_resource(
            AnyUrl("portfolio://proposal/ai_ml_engineer-prop-001"))
        assert json.loads(proposal.contents[0].text)["outcome"] in {"won", "replied", "ignored"}
        prompt = await session.get_prompt("draft_proposal", {"job_post": "Build a RAG bot."})
        assert "<job_post>\nBuild a RAG bot.\n</job_post>" in prompt.messages[0].content.text


@pytest.mark.skipif(not os.environ.get("REAL_EMBEDDINGS"),
                    reason="downloads the real model; run locally with REAL_EMBEDDINGS=1")
async def test_real_embedder_finds_the_matching_case_study() -> None:
    async with open_session("ai_ml_engineer", make_embedder(embeddings_config())) as session:
        result = await call(session, "search_evidence", requirement=CLINIC_BOT, k=3,
                            filters={"types": ["case_study"]})
    assert result["items"][0]["id"] == "ai-cs-01"
