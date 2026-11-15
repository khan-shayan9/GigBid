"""Workspace MCP tools through an in-memory MCP client, with the store in a temp folder."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session

from mcp_servers.workspace.server import WorkspaceSettings, create_server

# Friday 2026-11-20 to Monday 2026-11-23; ai_ml_engineer's profile timezone is UTC+5.
WINDOW = {"window_start": "2026-11-20T15:00:00+05:00", "window_end": "2026-11-23T23:00:00+05:00"}


@asynccontextmanager
async def open_session(tmp_path: Path, user: str = "ai_ml_engineer") -> AsyncIterator[ClientSession]:
    settings = WorkspaceSettings(stdio_user=user, store_dir=tmp_path)
    async with create_connected_server_and_client_session(create_server(settings)) as session:
        yield session


async def call(session: ClientSession, tool: str, **args: Any) -> dict[str, Any]:
    result = await session.call_tool(tool, args)
    assert not result.isError, result.content
    return result.structuredContent


async def error_of(session: ClientSession, tool: str, **args: Any) -> str:
    result = await session.call_tool(tool, args)
    assert result.isError
    return result.content[0].text.removeprefix(f"Error executing tool {tool}: ")


async def starts(session: ClientSession, **args: Any) -> list[str]:
    result = await call(session, "find_free_slots", **WINDOW, **args)
    return [slot["start"] for slot in result["slots"]]


async def test_free_slots_follow_working_hours_and_skip_weekends(tmp_path: Path) -> None:
    async with open_session(tmp_path) as session:
        slots = await starts(session, duration_minutes=60, limit=4)
    assert slots == ["2026-11-20T15:00:00+05:00", "2026-11-20T15:30:00+05:00",
                     "2026-11-20T16:00:00+05:00", "2026-11-23T09:00:00+05:00"]


async def test_hold_previews_then_books_once(tmp_path: Path) -> None:
    hold = {"start": "2026-11-23T09:00:00+05:00", "title": "Interview: clinic bot",
            "idempotency_key": "hold-0001", "duration_minutes": 60}
    async with open_session(tmp_path) as session:
        preview = await call(session, "hold_slot", **hold)
        assert preview["dry_run"] and preview["status"] == "tentative"
        assert "2026-11-23T09:00:00+05:00" in await starts(session, limit=20)
        booked = await call(session, "hold_slot", **hold, dry_run=False)
        again = await call(session, "hold_slot", **hold, dry_run=False)
        assert booked["hold_id"] == again["hold_id"]
        later = await starts(session, limit=20)
        assert "2026-11-23T09:00:00+05:00" not in later and "2026-11-23T09:30:00+05:00" not in later
        clash = hold | {"start": "2026-11-23T09:30:00+05:00", "idempotency_key": "hold-0002"}
        assert (await error_of(session, "hold_slot", **clash, dry_run=False)).startswith(
            "slot_taken")
        reused = hold | {"title": "Something else"}
        assert (await error_of(session, "hold_slot", **reused, dry_run=False)).startswith(
            "idempotency_conflict")
    async with open_session(tmp_path, "data_analyst") as session:  # holds are per user
        assert (await call(session, "hold_slot", **hold, dry_run=False))["hold_id"] != \
            booked["hold_id"]


async def test_times_must_carry_a_timezone(tmp_path: Path) -> None:
    async with open_session(tmp_path) as session:
        assert "timezone" in await error_of(
            session, "find_free_slots", window_start="2026-11-20T09:00:00",
            window_end="2026-11-21T09:00:00")
        assert (await error_of(session, "find_free_slots", window_start=WINDOW["window_end"],
                               window_end=WINDOW["window_start"])).startswith("invalid_window")


async def test_email_drafts_are_saved_once_and_never_sent(tmp_path: Path) -> None:
    email = {"to": "client@example.com", "subject": "Interview times",
             "body": "Monday 09:00 works for me.", "idempotency_key": "email-0001"}
    async with open_session(tmp_path) as session:
        assert (await call(session, "draft_email", **email))["dry_run"]
        assert not (tmp_path / "ai_ml_engineer.json").exists()
        first = await call(session, "draft_email", **email, dry_run=False)
        again = await call(session, "draft_email", **email, dry_run=False)
        assert first["draft_id"] == again["draft_id"] and first["status"] == "draft"
        assert "to" in await error_of(session, "draft_email", **email | {"to": "not-an-email"})
    assert (tmp_path / "ai_ml_engineer.json").read_text().count("draft_id") == 1
