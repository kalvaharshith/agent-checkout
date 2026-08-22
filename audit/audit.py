"""
Append-only audit trail.

One row per state transition, forever. The database itself refuses
UPDATE and DELETE on this table (see triggers) — append-only is
enforced by SQLite, not by convention.
"""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "audit.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    event_id TEXT NOT NULL UNIQUE,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT NOT NULL,
    auth_id TEXT,
    reason TEXT
);
CREATE TRIGGER IF NOT EXISTS audit_no_update
BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'append-only: UPDATE forbidden');
END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete
BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'append-only: DELETE forbidden');
END;
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    conn = _connect()
    try:
        with conn:
            conn.executescript(_SCHEMA)
    finally:
        conn.close()


def write_event(actor: str, action: str, detail: dict,
                auth_id: str | None = None, reason: str | None = None) -> str:
    """Append one event to the trail. Returns the event_id."""
    init_db()
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "INSERT INTO audit_events (ts, event_id, actor, action, detail, auth_id, reason) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    event_id,
                    actor,
                    action,
                    json.dumps(detail, default=str),
                    auth_id,
                    reason,
                ),
            )
    finally:
        conn.close()
    return event_id