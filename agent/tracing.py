"""Langfuse tracing (R8, E3): one trace per run thread, PII masked, off without keys.

The trace id is derived from the thread id, so every segment of a thread (the first run, the
resume after approval, a retry), wherever it runs (API task or worker), lands in one trace, and
the run viewer can link to it without storing anything. LangChain's callback records every node,
model call (tokens, latency) and tool call as a span. With LANGFUSE_PUBLIC_KEY and
LANGFUSE_SECRET_KEY unset, nothing is sent and no link is shown.
"""

import asyncio
import logging
import os
from functools import cache
from typing import Any

from data.pipeline.pii import mask_pii

log = logging.getLogger("gigbid.tracing")
HTTP_TIMEOUT_S = 5  # trace-link lookups must not stall the run viewer when Langfuse is down


def enabled() -> bool:
    return bool(os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"))


def trace_id_for(thread_id: str) -> str:
    from langfuse import Langfuse
    return Langfuse.create_trace_id(seed=thread_id)


def _mask(*, data: Any, **_: Any) -> Any:
    """Masks emails, URLs and phone numbers in everything sent to Langfuse."""
    if isinstance(data, str):
        return mask_pii(data)
    if isinstance(data, dict):
        return {key: _mask(data=value) for key, value in data.items()}
    if isinstance(data, list | tuple):
        return [_mask(data=value) for value in data]
    return data


@cache
def _client() -> Any:
    from langfuse import Langfuse
    return Langfuse(mask=_mask, environment=os.environ.get("APP_ENV", "development"),
                    timeout=HTTP_TIMEOUT_S)


def callbacks(thread_id: str) -> list[Any]:
    """LangChain callbacks that send this thread's spans to its trace ([] when tracing is off)."""
    if not enabled():
        return []
    from langfuse.langchain import CallbackHandler
    _client()  # the handler uses the masked client created here
    return [CallbackHandler(trace_context={"trace_id": trace_id_for(thread_id)})]


class _TracedTools:
    """An MCP client whose tool calls show up as spans under the node that made them."""

    def __init__(self, mcp: Any) -> None:
        self._mcp = mcp

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mcp, name)

    async def call(self, node: str, tool: str, args: dict[str, Any]) -> Any:
        from langchain_core.runnables import RunnableLambda

        async def run(arguments: dict[str, Any]) -> Any:
            return await self._mcp.call(node, tool, arguments)
        return await RunnableLambda(run, name=f"tool:{tool}").ainvoke(args)


def traced(mcp: Any) -> Any:
    """`mcp` with traced tool calls when tracing is on, else `mcp` itself."""
    return _TracedTools(mcp) if enabled() else mcp


def flush() -> None:
    """Send buffered spans now (at shutdown); never raises."""
    if enabled():
        try:
            _client().flush()
        except Exception as error:  # noqa: BLE001 - tracing must never fail a run
            log.warning("trace flush failed: %s", mask_pii(repr(error)))


async def trace_url(thread_id: str) -> str | None:
    """The thread's trace in the Langfuse UI, or None (tracing off, or Langfuse unreachable)."""
    if not enabled():
        return None
    try:  # the first call looks up the project id over HTTP
        return await asyncio.to_thread(_client().get_trace_url,
                                       trace_id=trace_id_for(thread_id))
    except Exception as error:  # noqa: BLE001 - a missing link must not break the run viewer
        log.warning("no trace link: %s", mask_pii(repr(error)))
        return None
