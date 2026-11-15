"""Pull a GitHub repo's README and code into a portfolio folder, through the GitHub MCP server.

The files land in `<portfolio>/repos/<repo>/`, where `load_portfolio` reads them like any other
repo, so the next `load_corpus` (the incremental re-index) embeds only the new files.
`call_tool` is the caller's MCP call for the `github_ingest` allowlist (agent/mcp_client.py),
so `rag/` never holds a token or opens a connection itself.

shortcut: top-level files only, no recursion into folders; recurse when users' repos keep their
code below the root.
"""

import json
import re
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from rag.ingest.portfolio import REPO_SUFFIXES

CallTool = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]
SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
MAX_FILES = 20
MAX_FILE_CHARS = 50_000  # one file larger than this is likely generated or vendored


async def fetch_github_repo(owner: str, repo: str, portfolio_dir: Path,
                            call_tool: CallTool) -> list[Path]:
    """Save the repo's top-level text files under repos/<repo>/; returns the files written."""
    if not (SAFE_NAME.match(owner) and SAFE_NAME.match(repo)):
        raise ValueError("owner and repo must be plain GitHub names")
    listing = await call_tool("get_file_contents", {"owner": owner, "repo": repo, "path": "/"})
    names = [entry["name"] for entry in _entries(listing)
             if entry.get("type") == "file" and SAFE_NAME.match(entry.get("name", ""))
             and Path(entry["name"]).suffix in REPO_SUFFIXES][:MAX_FILES]
    target = portfolio_dir / "repos" / repo
    written = []
    for name in names:
        result = await call_tool("get_file_contents",
                                 {"owner": owner, "repo": repo, "path": name})
        text = max(result.get("content", []), key=len, default="")
        if not text or len(text) > MAX_FILE_CHARS:
            continue
        target.mkdir(parents=True, exist_ok=True)
        (target / name).write_text(text, encoding="utf-8")
        written.append(target / name)
    return written


def _entries(result: dict[str, Any]) -> list[dict[str, Any]]:
    """The directory listing: the first text part that parses as a JSON list."""
    for text in result.get("content", []):
        try:
            parsed = json.loads(text)
        except ValueError:
            continue
        if isinstance(parsed, list):
            return [entry for entry in parsed if isinstance(entry, dict)]
    return []


async def _main(user: str, owner: str, repo: str, portfolio_dir: Path) -> None:
    from agent.mcp_client import McpClient  # CLI only; the library code takes call_tool

    async with McpClient(user, servers=["github"]) as mcp:
        files = await fetch_github_repo(
            owner, repo, portfolio_dir,
            lambda tool, args: mcp.call("github_ingest", tool, args))
    print(f"wrote {len(files)} files to {portfolio_dir / 'repos' / repo}")


if __name__ == "__main__":
    # python -m rag.ingest.github <user> <owner>/<repo> <portfolio dir>
    import asyncio

    from dotenv import load_dotenv

    load_dotenv()
    owner_name, repo_name = sys.argv[2].split("/", 1)
    asyncio.run(_main(sys.argv[1], owner_name, repo_name, Path(sys.argv[3])))
