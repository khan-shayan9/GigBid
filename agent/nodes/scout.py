"""Scout: run the user's saved searches and de-duplicate the jobs they return.

A job seen twice (same id, or the same title and text reposted under a new id) is kept once.
shortcut: runs when the inbox loads; the Phase 7 worker runs it on a schedule and queues jobs.
"""

import hashlib
from typing import Any

from agent.mcp_client import McpClient

NODE = "scout"


def content_hash(job: dict[str, Any]) -> str:
    text = f"{job['title']}\n{job['description']}".lower()
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()


async def scout_jobs(mcp: McpClient, searches: list[str], limit: int) -> list[dict[str, Any]]:
    """Newest-first jobs from every saved search (all open jobs when there is none)."""
    jobs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for query in searches or [""]:
        page = await mcp.call(NODE, "search_jobs", {"query": query, "limit": limit})
        for job in page["jobs"]:
            keys = {job["job_id"], content_hash(job)}
            if keys & seen:
                continue
            seen |= keys
            jobs.append(job)
    return sorted(jobs, key=lambda job: job["posted_at"], reverse=True)
