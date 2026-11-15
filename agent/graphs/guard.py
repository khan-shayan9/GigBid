"""Failure handling and budgets around every graph node (C4, C7).

- A dependency that is down (ToolUnavailable: server gone, timeout, GigSim 429 or 5xx after the
  MCP client's own retries) gets a few more tries with backoff, then the thread is dead-lettered.
- A refused tool call or an LLM error that survived the model's retries dead-letters at once.
- Every node adds to the thread's step and token counts; over budget -> "needs_attention".
Once `status` is set, guarded nodes do nothing and the graph's routers end the thread.
Retrying a node is safe: reads are idempotent and write tools carry idempotency keys.
"""

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.callbacks import get_usage_metadata_callback
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from openai import APIError

from agent.config import load_config
from agent.mcp_client import ToolFailed, ToolNotAllowed, ToolUnavailable

Node = Callable[..., Awaitable[dict[str, Any]]]  # (state) or (state, config)
FATAL_ERRORS = (ToolFailed, ToolNotAllowed, APIError)


def guarded(name: str, node: Node) -> Node:
    async def run(state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        if state.get("status"):
            return {}
        budgets = load_config()["budgets"]
        with get_usage_metadata_callback() as usage:
            update = await _with_retries(name, node, state, config, budgets)
        tokens = sum(item.get("total_tokens", 0) for item in usage.usage_metadata.values())
        update = update | {"steps": 1, "tokens_used": tokens}
        if update.get("status"):
            return update
        steps, used = state.get("steps", 0) + 1, state.get("tokens_used", 0) + tokens
        if steps > budgets["max_graph_steps"] or used > budgets["max_tokens_per_job"]:
            reason = (f"budget exceeded after {name}: {steps}/{budgets['max_graph_steps']} steps, "
                      f"{used}/{budgets['max_tokens_per_job']} tokens")
            update |= {"status": "needs_attention", "errors": [reason]}
        return update

    return run


async def _with_retries(name: str, node: Node, state: dict[str, Any], config: RunnableConfig,
                        budgets: dict[str, Any]) -> dict[str, Any]:
    attempts = 1 + budgets["node_retries"]
    args = (state, config) if len(inspect.signature(node).parameters) == 2 else (state,)
    for attempt in range(attempts):
        try:
            return await node(*args)
        except ToolUnavailable as error:
            if attempt == attempts - 1:
                return _dead_letter(name, error)
            await asyncio.sleep(budgets["node_backoff_s"] * 2 ** attempt)
        except FATAL_ERRORS as error:
            return _dead_letter(name, error)
    raise AssertionError("unreachable")


def _dead_letter(name: str, error: Exception) -> dict[str, Any]:
    return {"status": "dead_letter", "errors": [f"{name}: {type(error).__name__}: {error}"]}


def halts(route: Callable[[Any], str]) -> Callable[[Any], str]:
    """Wrap a router so a thread with a `status` (dead-lettered or over budget) ends."""
    def check(state: dict[str, Any]) -> str:
        return END if state.get("status") else route(state)

    return check
