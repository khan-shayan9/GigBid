"""Phase 3 acceptance: one agent drafts one grounded proposal for a GigSim job, through MCP only.

Needs GigSim running (`make gigsim`) and GROQ_API_KEY. Writes evals/results/phase3_grounded_draft.json.
Run: `uv run python -m evals.runners.draft_one --user ai_ml_engineer --query chatbot`.
"""

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from agent.config import load_config
from agent.llm import chat_model
from agent.mcp_client import McpClient
from agent.nodes.writer import NODE, draft_proposal, gather_evidence

RESULT = Path(__file__).resolve().parents[1] / "results" / "phase3_grounded_draft.json"


async def run(user: str, query: str) -> dict:
    async with McpClient(user, servers=["portfolio", "marketplace"]) as mcp:
        jobs = (await mcp.call("scout", "search_jobs", {"query": query, "limit": 1}))["jobs"]
        if not jobs:
            raise SystemExit(f"no GigSim job matches {query!r}")
        job = jobs[0]
        model = chat_model(NODE)
        started = time.perf_counter()
        draft, evidence = await draft_proposal(job, mcp, model)
        seconds = round(time.perf_counter() - started, 1)
        # Grounded: every cited id is one that search_evidence returned for this job.
        retrieved = set(await gather_evidence(job, mcp))
    return {
        "at": datetime.now(UTC).isoformat(), "user": user, "query": query,
        "job_id": job["job_id"], "job_title": job["title"],
        "model": model.model_name, "profile": load_config()["models"]["profile"],
        "cover_letter": draft.cover_letter, "evidence_ids": draft.evidence_ids,
        "evidence": [{key: item[key] for key in ("id", "type", "title", "source", "score")}
                     for item in evidence],
        "grounded": bool(draft.evidence_ids) and set(draft.evidence_ids) <= retrieved,
        "draft_seconds": seconds, "unavailable_servers": sorted(mcp.unavailable),
    }


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="ai_ml_engineer")
    parser.add_argument("--query", default="chatbot")
    args = parser.parse_args()
    result = asyncio.run(run(args.user, args.query))
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
