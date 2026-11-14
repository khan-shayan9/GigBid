"""SQLite state that must survive a restart: clock, Connects ledger, proposals, events,
messages and idempotency records."""

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS connects_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, delta INTEGER NOT NULL,
    reason TEXT NOT NULL, at_min REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS proposals (
    proposal_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, job_id TEXT NOT NULL,
    client_id TEXT NOT NULL, cover_letter TEXT NOT NULL, bid_type TEXT NOT NULL,
    bid_amount_usd REAL NOT NULL, screening_json TEXT NOT NULL, created_min REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, proposal_id TEXT NOT NULL, user_id TEXT NOT NULL,
    type TEXT NOT NULL, at_min REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, thread_id TEXT NOT NULL,
    job_id TEXT NOT NULL, client_id TEXT NOT NULL, sender TEXT NOT NULL, text TEXT NOT NULL,
    at_min REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency (
    user_id TEXT NOT NULL, key TEXT NOT NULL, body_hash TEXT NOT NULL, response TEXT NOT NULL,
    PRIMARY KEY (user_id, key)
);
"""
STATE_TABLES = ("connects_ledger", "proposals", "events", "messages", "idempotency")


class StateDB:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # FastAPI runs sync routes in a thread pool; one connection guarded by a lock is enough here.
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._conn.executescript(SCHEMA)

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        """One atomic transaction; an exception inside rolls everything back."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

    def rows(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def get_meta(self, key: str) -> str | None:
        found = self.rows("SELECT value FROM meta WHERE key = ?", (key,))
        return found[0]["value"] if found else None

    def set_meta(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def connects_delta(self, user_id: str, conn: sqlite3.Connection | None = None) -> int:
        """Net Connects change for a user (spends are negative)."""
        sql = "SELECT COALESCE(SUM(delta), 0) AS total FROM connects_ledger WHERE user_id = ?"
        if conn is not None:
            return int(conn.execute(sql, (user_id,)).fetchone()["total"])
        return int(self.rows(sql, (user_id,))[0]["total"])

    def reset(self) -> None:
        with self.tx() as conn:
            for table in STATE_TABLES:
                conn.execute(f"DELETE FROM {table}")  # fixed table names, no user input
            conn.execute("DELETE FROM meta WHERE key = 'offset_min'")

    def close(self) -> None:
        self._conn.close()
