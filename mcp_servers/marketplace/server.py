"""Marketplace MCP server: GigSim (or live Upwork) behind typed tools, auth, rate limit and audit.

Run: `python -m mcp_servers.marketplace.server` (stdio, for MCP Inspector or Claude Desktop) or
`python -m mcp_servers.marketplace.server http` (Streamable HTTP with Bearer auth).
"""

import json
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from dotenv import load_dotenv
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from agent.config import load_config
from agent.marketplace_port import MarketplaceError, MarketplacePort, MarketplaceUnavailable
from data.pipeline.pii import mask_pii
from mcp_servers.auth import RateLimiter, parse_tokens
from mcp_servers.common import (
    REPO_ROOT,
    HttpSettings,
    http_settings_from_env,
    new_server,
    serve,
    session_user,
)
from mcp_servers.marketplace.adapters import upwork_live
from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter
from mcp_servers.marketplace.schemas import (
    ClientHistory,
    ConnectsBalance,
    JobPage,
    MarketRates,
    Message,
    MessageList,
    Proposal,
    ProposalList,
    SubmitResult,
)
from mcp_servers.marketplace.schemas import Job as JobOut

# No "/" or "." in ids: they become GigSim URL path segments.
Id = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_:~-]+$")]
IdempotencyKey = Annotated[str, Field(
    min_length=8, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$",
    description="Reuse the same key when retrying; a repeated key never acts twice.",
)]
DryRun = Annotated[bool, Field(
    description="True (default) returns exactly what would be sent and what it costs, and "
                "changes nothing. False is allowed only after the user approved.",
)]

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
DRAFT = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True,
                        openWorldHint=True)
SPEND = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True,
                        openWorldHint=True)
SEND = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True,
                       openWorldHint=True)


class ServerSettings(HttpSettings):
    rate_per_minute: int = Field(20, ge=1)  # stays under GigSim's 30-call burst per user
    audit_path: Path = REPO_ROOT / "data" / "processed" / "audit" / "marketplace.jsonl"
    public_url: str = "http://localhost:8082"
    port: int = 8082


def create_server(settings: ServerSettings, port_for: Callable[[str], MarketplacePort]) -> FastMCP:
    mcp = new_server("gigbid-marketplace",
                     "Freelance marketplace: read jobs, clients and messages; write drafts, "
                     "submissions and messages only after human approval.", settings)
    limiter = RateLimiter(settings.rate_per_minute)

    async def run(ctx: Context, tool: str, args: dict[str, Any],
                  call: Callable[[MarketplacePort], Awaitable[dict[str, Any]]]) -> dict[str, Any]:
        user = session_user(settings)
        trace_id = _trace_id(ctx)

        def refuse(code: str, message: str) -> ToolError:
            _audit(settings.audit_path, user or "-", tool, args, {"error": code}, trace_id)
            return ToolError(f"{code}: {message}")

        if not user:
            raise refuse("unauthenticated", "no user for this session")
        wait = limiter.retry_after(user)
        if wait:
            raise refuse("rate_limited", f"retry after {wait:.1f} s")
        try:
            result = await call(port_for(user))
        except MarketplaceError as error:
            raise refuse(error.code, error.message) from error
        except MarketplaceUnavailable as error:
            raise refuse("marketplace_unavailable", str(error)) from error
        except ToolError:
            raise
        except Exception as error:  # audit the unexpected too, then let FastMCP report it
            _audit(settings.audit_path, user, tool, args, {"error": "internal_error"}, trace_id)
            raise ToolError("internal_error: the marketplace server failed") from error
        _audit(settings.audit_path, user, tool, args, result, trace_id)
        return result

    @mcp.tool(annotations=READ)
    async def search_jobs(
        ctx: Context,
        query: Annotated[str, Field(max_length=200, description="All words must appear")] = "",
        skills: Annotated[list[str], Field(max_length=20, description="Any may match")] = [],  # noqa: B006
        payment_type: Literal["fixed", "hourly"] | None = None,
        since: Annotated[datetime | None, Field(description="Only jobs posted after this")] = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> JobPage:
        """Search open jobs, newest first."""
        args = {"query": query, "skills": skills, "payment_type": payment_type,
                "since": since.isoformat() if since else None, "limit": limit, "offset": offset}
        return JobPage.model_validate(await run(ctx, "search_jobs", args,
                                                lambda port: port.search_jobs(**args)))

    @mcp.tool(annotations=READ)
    async def get_job(ctx: Context, job_id: Id) -> JobOut:
        """Get one job post with its Connects cost."""
        return JobOut.model_validate(await run(ctx, "get_job", {"job_id": job_id},
                                               lambda port: port.get_job(job_id)))

    @mcp.tool(annotations=READ)
    async def get_client_history(ctx: Context, client_id: Id) -> ClientHistory:
        """Get a client's profile and past contracts (spend, rating, feedback)."""
        args = {"client_id": client_id}
        return ClientHistory.model_validate(
            await run(ctx, "get_client_history", args,
                      lambda port: port.get_client_history(client_id)))

    @mcp.tool(annotations=READ)
    async def get_connects_balance(ctx: Context) -> ConnectsBalance:
        """Get the user's Connects balance."""
        return ConnectsBalance.model_validate(
            await run(ctx, "get_connects_balance", {}, lambda port: port.get_connects_balance()))

    @mcp.tool(annotations=READ)
    async def get_market_rates(ctx: Context) -> MarketRates:
        """Get market price statistics per job domain (hourly and fixed-price percentiles)."""
        return MarketRates.model_validate(
            await run(ctx, "get_market_rates", {}, lambda port: port.get_market_rates()))

    @mcp.tool(annotations=READ)
    async def list_messages(
        ctx: Context, thread_id: Id | None = None,
        since: Annotated[datetime | None, Field(description="Only messages after this")] = None,
        limit: Annotated[int, Field(ge=1, le=500)] = 100,
    ) -> MessageList:
        """List client conversation messages, oldest first; filter by thread or time."""
        args = {"thread_id": thread_id, "since": since.isoformat() if since else None,
                "limit": limit}
        return MessageList.model_validate(await run(ctx, "list_messages", args,
                                                    lambda port: port.list_messages(**args)))

    @mcp.tool(annotations=READ)
    async def list_proposals(ctx: Context) -> ProposalList:
        """List the user's proposals, newest first, each with its lifecycle status."""
        return ProposalList.model_validate(
            await run(ctx, "list_proposals", {}, lambda port: port.list_proposals()))

    @mcp.tool(annotations=DRAFT)
    async def create_proposal_draft(
        ctx: Context, job_id: Id,
        cover_letter: Annotated[str, Field(min_length=1, max_length=5000)],
        bid_type: Literal["fixed", "hourly"],
        bid_amount_usd: Annotated[float, Field(gt=0, le=1_000_000)],
        idempotency_key: IdempotencyKey,
        screening_answers: Annotated[list[str], Field(max_length=20)] = [],  # noqa: B006
        dry_run: DryRun = True,
    ) -> Proposal:
        """Create a proposal draft on the marketplace (not sent to the client, costs nothing)."""
        payload = {"job_id": job_id, "cover_letter": cover_letter,
                   "bid": {"type": bid_type, "amount_usd": bid_amount_usd},
                   "screening_answers": screening_answers}
        args = {**payload, "idempotency_key": idempotency_key, "dry_run": dry_run}
        return Proposal.model_validate(await run(
            ctx, "create_proposal_draft", args,
            lambda port: port.create_proposal_draft(payload, idempotency_key, dry_run)))

    @mcp.tool(annotations=SPEND)
    async def submit_proposal(
        ctx: Context, proposal_id: Id, idempotency_key: IdempotencyKey, dry_run: DryRun = True,
    ) -> SubmitResult:
        """Submit a drafted proposal to the client. Spends the job's Connects cost."""
        args = {"proposal_id": proposal_id, "idempotency_key": idempotency_key,
                "dry_run": dry_run}
        return SubmitResult.model_validate(await run(
            ctx, "submit_proposal", args,
            lambda port: port.submit_proposal(proposal_id, idempotency_key, dry_run)))

    @mcp.tool(annotations=SEND)
    async def send_message(
        ctx: Context, thread_id: Id,
        text: Annotated[str, Field(min_length=1, max_length=3000)],
        idempotency_key: IdempotencyKey, dry_run: DryRun = True,
    ) -> Message:
        """Send a message to the client in a proposal or conversation thread."""
        args = {"thread_id": thread_id, "text": text, "idempotency_key": idempotency_key,
                "dry_run": dry_run}
        return Message.model_validate(await run(
            ctx, "send_message", args,
            lambda port: port.send_message(thread_id, text, idempotency_key, dry_run)))

    return mcp


def _trace_id(ctx: Context) -> str:
    """The caller's trace id from the request's `_meta.trace_id`, or a new one."""
    meta = ctx.request_context.meta
    extra = (meta.model_extra or {}) if meta else {}
    return str(extra.get("trace_id") or uuid.uuid4())


def _audit(path: Path, user: str, tool: str, args: dict[str, Any], result: dict[str, Any],
           trace_id: str) -> None:
    """Append one masked line per call. The file is only ever appended to."""
    record = {"at": datetime.now(UTC).isoformat(), "user": user, "tool": tool,
              "arguments": _masked(args), "result": _masked(result), "trace_id": trace_id}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as log:
        log.write(json.dumps(record) + "\n")


def _masked(value: Any) -> Any:
    if isinstance(value, str):
        return mask_pii(value)
    if isinstance(value, dict):
        return {key: _masked(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_masked(item) for item in value]
    return value


def settings_from_env() -> tuple[ServerSettings, Callable[[str], MarketplacePort]]:
    env = os.environ
    gigsim_tokens = {user: token for token, user in
                     parse_tokens(env.get("GIGSIM_TOKENS", ""), "GIGSIM_TOKENS").items()}
    settings = ServerSettings(
        **http_settings_from_env("MARKETPLACE", ServerSettings().public_url, 8082),
        rate_per_minute=int(env.get("MARKETPLACE_RATE_PER_MINUTE", "20")),
        audit_path=Path(env.get("MARKETPLACE_AUDIT_LOG", ServerSettings().audit_path)),
    )
    base_url = env.get("GIGSIM_BASE_URL", "http://localhost:8081")
    adapters: dict[str, MarketplacePort] = {}

    mode = env.get("MARKETPLACE_MODE") or load_config()["marketplace"]["mode"]

    def port_for(user: str) -> MarketplacePort:
        if mode == "upwork_live":
            if user not in adapters:
                adapters[user] = upwork_live.adapter_for(user)
            return adapters[user]
        if user not in gigsim_tokens:
            raise ToolError(f"unauthenticated: no GigSim token for {user!r}")
        if user not in adapters:
            adapters[user] = GigSimAdapter(base_url, gigsim_tokens[user])
        return adapters[user]

    return settings, port_for


if __name__ == "__main__":
    load_dotenv()
    server_settings, port_factory = settings_from_env()
    serve(server_settings, lambda settings: create_server(settings, port_factory), "MARKETPLACE")
