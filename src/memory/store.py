"""SQLite-backed key/value memory with optional tags and timestamps."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    tags TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);
"""


@contextmanager
def _connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Yield a connection returning :class:`sqlite3.Row` rows; commit on success, always close."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_store(db_path: Path) -> None:
    """Create the memory database and table if missing."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)


def remember(db_path: Path, key: str, value: str, tags: list[str] | None = None) -> dict:
    """Insert or replace a memory under ``key``."""
    now = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO memories (key, value, tags, updated_at) VALUES (?,?,?,?)",
            (key, value, ",".join(tags or []), now),
        )
    return {"key": key, "value": value, "tags": tags or [], "updated_at": now}


def recall(db_path: Path, key: str) -> dict | None:
    """Return the memory stored under ``key`` or ``None``."""
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM memories WHERE key = ?", (key,)).fetchone()
    return _row_to_dict(row) if row else None


def list_memories(db_path: Path, tag: str | None = None, contains: str | None = None) -> list[dict]:
    """List memories, optionally filtered by tag or by a substring of key/value."""
    sql, params = "SELECT * FROM memories WHERE 1=1", []
    if tag:
        sql += " AND (',' || tags || ',') LIKE ?"
        params.append(f"%,{tag},%")
    if contains:
        sql += " AND (key LIKE ? OR value LIKE ?)"
        params += [f"%{contains}%", f"%{contains}%"]
    with _connect(db_path) as conn:
        rows = conn.execute(sql + " ORDER BY updated_at DESC", params).fetchall()
    return [_row_to_dict(r) for r in rows]


def forget(db_path: Path, key: str) -> bool:
    """Delete the memory under ``key``. Returns ``True`` if it existed."""
    with _connect(db_path) as conn:
        return conn.execute("DELETE FROM memories WHERE key = ?", (key,)).rowcount > 0


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a memory row to a dict with ``tags`` as a list."""
    return {
        "key": row["key"],
        "value": row["value"],
        "tags": [t for t in row["tags"].split(",") if t],
        "updated_at": row["updated_at"],
    }
