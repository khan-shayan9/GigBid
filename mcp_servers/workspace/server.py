"""Workspace MCP server: a local mock calendar (free slots, tentative holds) and email drafts.

shortcut: the calendar is weekdays 09:00-17:00 in the user's profile timezone, busy only where
GigBid placed holds, stored in one JSON file per user; email drafts are saved, never sent.
A real calendar or mail connector would replace the store behind the same tools.

Run: `python -m mcp_servers.workspace.server` (stdio) or `... http` (Streamable HTTP, Bearer auth).
"""

import asyncio
import json
import re
import uuid
from datetime import UTC, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import AwareDatetime, BaseModel, Field

from mcp_servers.common import (
    REPO_ROOT,
    HttpSettings,
    http_settings_from_env,
    new_server,
    serve,
    session_user,
)

USER = re.compile(r"^[a-z0-9_]+$")
UTC_OFFSET = re.compile(r"^UTC(?P<sign>[+-])(?P<hours>\d{1,2})$")
SLOT_STEP = timedelta(minutes=30)
MAX_WINDOW = timedelta(days=14)
READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True,
                        openWorldHint=False)
Minutes = Annotated[int, Field(ge=15, le=240)]
IdempotencyKey = Annotated[str, Field(
    min_length=8, max_length=200, pattern=r"^[A-Za-z0-9._:-]+$",
    description="Reuse the same key when retrying; a repeated key never acts twice.")]
DryRun = Annotated[bool, Field(
    description="True (default) shows the result and changes nothing. False is allowed only "
                "after the user approved.")]


class WorkspaceSettings(HttpSettings):
    store_dir: Path = REPO_ROOT / "data" / "processed" / "workspace"
    personas_dir: Path = REPO_ROOT / "data" / "personas"  # for each user's profile timezone
    workday_start: time = time(9)
    workday_end: time = time(17)
    public_url: str = "http://localhost:8084"
    port: int = 8084


class Slot(BaseModel):
    start: datetime
    end: datetime


class SlotList(BaseModel):
    slots: list[Slot]
    timezone: str


class Hold(Slot):
    hold_id: str
    title: str
    status: Literal["tentative"] = "tentative"
    dry_run: bool


class EmailDraft(BaseModel):
    draft_id: str
    to: str
    subject: str
    body: str
    status: Literal["draft"] = "draft"  # this server never sends email
    dry_run: bool


def create_server(settings: WorkspaceSettings) -> FastMCP:
    mcp = new_server("gigbid-workspace",
                     "The freelancer's calendar and email drafts: find free interview slots, "
                     "hold one tentatively, draft an email. Nothing is ever sent.", settings)
    lock = asyncio.Lock()

    def current_user() -> str:
        user = session_user(settings)
        if not user or not USER.match(user):
            raise ToolError("unauthenticated: no user for this session")
        return user

    def load(user: str) -> dict:
        path = settings.store_dir / f"{user}.json"
        if not path.exists():
            return {"holds": [], "drafts": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def save(user: str, store: dict) -> None:
        settings.store_dir.mkdir(parents=True, exist_ok=True)
        (settings.store_dir / f"{user}.json").write_text(json.dumps(store, indent=1),
                                                         encoding="utf-8")

    def zone(user: str) -> timezone:
        profile = settings.personas_dir / user / "profile.json"
        label = json.loads(profile.read_text(encoding="utf-8")).get("timezone", "UTC") \
            if profile.exists() else "UTC"
        match = UTC_OFFSET.match(label)
        if not match:
            return UTC
        hours = int(match["hours"]) * (1 if match["sign"] == "+" else -1)
        return timezone(timedelta(hours=hours), label)

    @mcp.tool(annotations=READ)
    async def find_free_slots(
        window_start: AwareDatetime, window_end: AwareDatetime, duration_minutes: Minutes = 30,
        limit: Annotated[int, Field(ge=1, le=20)] = 5,
    ) -> SlotList:
        """Free slots inside working hours (weekdays, the user's timezone), earliest first."""
        if not timedelta(0) < window_end - window_start <= MAX_WINDOW:
            raise ToolError("invalid_window: the window must be positive and at most 14 days")
        user = current_user()
        tz = zone(user)
        busy = [(datetime.fromisoformat(h["start"]), datetime.fromisoformat(h["end"]))
                for h in load(user)["holds"]]
        length = timedelta(minutes=duration_minutes)
        slots: list[Slot] = []
        day = window_start.astimezone(tz).date()
        while len(slots) < limit and day <= window_end.astimezone(tz).date():
            start = datetime.combine(day, settings.workday_start, tz)
            day_end = datetime.combine(day, settings.workday_end, tz)
            while day.weekday() < 5 and start + length <= day_end and len(slots) < limit:
                end = start + length
                if (start >= window_start and end <= window_end
                        and not any(start < taken_end and taken_start < end
                                    for taken_start, taken_end in busy)):
                    slots.append(Slot(start=start, end=end))
                start += SLOT_STEP
            day += timedelta(days=1)
        return SlotList(slots=slots, timezone=tz.tzname(None) or "UTC")

    @mcp.tool(annotations=WRITE)
    async def hold_slot(
        start: AwareDatetime, title: Annotated[str, Field(min_length=1, max_length=200)],
        idempotency_key: IdempotencyKey, duration_minutes: Minutes = 30, dry_run: DryRun = True,
    ) -> Hold:
        """Place a tentative hold on the calendar, e.g. for an interview the client may accept."""
        user = current_user()
        end = start + timedelta(minutes=duration_minutes)
        async with lock:
            store = load(user)
            request = {"start": start.isoformat(), "end": end.isoformat(), "title": title}
            previous = replay(store["holds"], idempotency_key, request)
            if previous:
                return Hold(**previous, dry_run=False)
            if any(start < datetime.fromisoformat(h["end"])
                   and datetime.fromisoformat(h["start"]) < end for h in store["holds"]):
                raise ToolError("slot_taken: another hold overlaps this time")
            hold = {"hold_id": new_id("hold", dry_run), **request}
            if not dry_run:
                store["holds"].append(hold | {"key": idempotency_key})
                save(user, store)
        return Hold(**hold, dry_run=dry_run)

    @mcp.tool(annotations=WRITE)
    async def draft_email(
        to: Annotated[str, Field(max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")],
        subject: Annotated[str, Field(min_length=1, max_length=200)],
        body: Annotated[str, Field(min_length=1, max_length=5000)],
        idempotency_key: IdempotencyKey, dry_run: DryRun = True,
    ) -> EmailDraft:
        """Save an email draft for the user to review and send themselves. Never sends."""
        user = current_user()
        async with lock:
            store = load(user)
            request = {"to": to, "subject": subject, "body": body}
            previous = replay(store["drafts"], idempotency_key, request)
            if previous:
                return EmailDraft(**previous, dry_run=False)
            draft = {"draft_id": new_id("draft", dry_run), **request}
            if not dry_run:
                store["drafts"].append(draft | {"key": idempotency_key})
                save(user, store)
        return EmailDraft(**draft, dry_run=dry_run)

    return mcp


def replay(records: list[dict], key: str, request: dict) -> dict | None:
    """The record stored under this idempotency key, if the request is the same one."""
    previous = next((record for record in records if record["key"] == key), None)
    if previous and any(previous[field] != value for field, value in request.items()):
        raise ToolError("idempotency_conflict: this key was used for a different request")
    return previous


def new_id(kind: str, dry_run: bool) -> str:
    return f"{kind}-preview" if dry_run else f"{kind}-{uuid.uuid4().hex[:12]}"


if __name__ == "__main__":
    load_dotenv()
    serve(WorkspaceSettings(**http_settings_from_env("WORKSPACE", "http://localhost:8084", 8084)),
          create_server, "WORKSPACE")
