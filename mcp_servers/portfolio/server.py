"""Portfolio MCP server: read-only evidence search over the signed-in user's own portfolio.

Run: `python -m mcp_servers.portfolio.server` (stdio) or `... http` (Streamable HTTP, Bearer auth).
`... warm` embeds every persona's portfolio once, so the first search does not wait for it.
The retrieval variant, index backend and reranker come from agent/config.yaml (`rag`).
Each user sees only `data/personas/<user>/`; the user comes from the Bearer token (or the stdio
user), never from a tool argument.
"""

import os
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
from rag.index.corpus import load_corpus, make_index
from rag.index.embedder import Embedder, make_embedder
from rag.retriever import Retriever, VariantSettings
from rag.variants.v3_rerank import Reranker, make_reranker

CONFIG_PATH = REPO_ROOT / "agent" / "config.yaml"


def create_server(settings: PortfolioSettings, embedder: Embedder,
                  reranker: Reranker | None = None, rag_config: dict | None = None) -> FastMCP:
    """`rag_config` defaults to agent/config.yaml. The tool path searches one requirement at a
    time, so V1's split is the caller's job; V8 refuses without rewriting (no model here)."""
    mcp = new_server("gigbid-portfolio",
                     "The freelancer's own portfolio: find evidence for a job's requirements "
                     "and cite its id.", settings)
    rag_config = rag_config or load_yaml()["rag"]
    store = PortfolioStore(settings, make_index(rag_config, embedder, settings.cache_dir),
                           rag_config, Retriever(rag_config, reranker=reranker))
    register_tools(mcp, store)
    register_resources(mcp, store)
    register_prompts(mcp)
    return mcp


def load_yaml() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def embeddings_config() -> dict:
    return load_yaml()["models"]["embeddings"]


def reranker_for(config: dict) -> Reranker | None:
    """The configured reranker, loaded only if the active variant uses one."""
    rag = config["rag"]
    settings = VariantSettings(**rag["variants"][os.environ.get("RAG_VARIANT") or rag["variant"]])
    needed = settings.rerank or settings.corrective
    return make_reranker(config["models"]["reranker"]) if needed else None


def warm(settings: PortfolioSettings, embedder: Embedder) -> None:
    """Embed every persona folder into the configured index (and the on-disk cache)."""
    rag_config = load_yaml()["rag"]
    index = make_index(rag_config, embedder, settings.cache_dir)
    for persona_dir in sorted(Path(settings.personas_dir).iterdir()):
        if persona_dir.is_dir():
            report = load_corpus(persona_dir, index, rag_config).last_sync
            print(f"indexed {persona_dir.name}: {report}")


if __name__ == "__main__":
    load_dotenv()
    portfolio_settings = PortfolioSettings(
        **http_settings_from_env("PORTFOLIO", "http://localhost:8083", 8083))
    if sys.argv[1:] == ["warm"]:
        warm(portfolio_settings, make_embedder(embeddings_config()))
    else:
        serve(portfolio_settings,
              lambda settings: create_server(settings, make_embedder(embeddings_config()),
                                             reranker_for(load_yaml())),
              "PORTFOLIO")
