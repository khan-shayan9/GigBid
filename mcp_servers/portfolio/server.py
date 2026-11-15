"""Portfolio MCP server: read-only evidence search over the signed-in user's own portfolio.

Run: `python -m mcp_servers.portfolio.server` (stdio) or `... http` (Streamable HTTP, Bearer auth).
`... warm` embeds every persona's portfolio once, so the first search does not wait for it.
Each user sees only `data/personas/<user>/`; the user comes from the Bearer token (or the stdio
user), never from a tool argument.
"""

import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from mcp_servers.common import REPO_ROOT, http_settings_from_env, new_server, serve
from mcp_servers.portfolio.prompts import register_prompts
from mcp_servers.portfolio.resources import register_resources
from mcp_servers.portfolio.store import PortfolioSettings, PortfolioStore
from mcp_servers.portfolio.tools import register_tools
from rag.index.embedder import Embedder, make_embedder
from rag.index.memory import build_index
from rag.ingest.portfolio import load_portfolio

CONFIG_PATH = REPO_ROOT / "agent" / "config.yaml"


def create_server(settings: PortfolioSettings, embedder: Embedder) -> FastMCP:
    mcp = new_server("gigbid-portfolio",
                     "The freelancer's own portfolio: find evidence for a job's requirements "
                     "and cite its id.", settings)
    store = PortfolioStore(settings, embedder)
    register_tools(mcp, store)
    register_resources(mcp, store)
    register_prompts(mcp)
    return mcp


def embeddings_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["models"]["embeddings"]


def warm(settings: PortfolioSettings, embedder: Embedder) -> None:
    """Fill the embedding cache for every persona folder."""
    for persona_dir in sorted(Path(settings.personas_dir).iterdir()):
        if (persona_dir / "cv.md").exists():
            build_index(load_portfolio(persona_dir), embedder, settings.cache_dir)
            print(f"embedded {persona_dir.name}")


if __name__ == "__main__":
    load_dotenv()
    portfolio_settings = PortfolioSettings(
        **http_settings_from_env("PORTFOLIO", "http://localhost:8083", 8083))
    if sys.argv[1:] == ["warm"]:
        warm(portfolio_settings, make_embedder(embeddings_config()))
    else:
        serve(portfolio_settings,
              lambda settings: create_server(settings, make_embedder(embeddings_config())),
              "PORTFOLIO")
