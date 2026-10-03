"""SQLite database access with a seeded sample schema.

The sample schema models a small security-operations dataset (hosts and
incidents) so agents have something meaningful to query.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SEED_SQL = """
CREATE TABLE IF NOT EXISTS hosts (
    id INTEGER PRIMARY KEY,
    hostname TEXT NOT NULL,
    ip TEXT NOT NULL,
    os TEXT,
    role TEXT
);
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY,
    host_id INTEGER REFERENCES hosts(id),
    severity TEXT CHECK (severity IN ('low','medium','high','critical')),
    category TEXT,
    description TEXT,
    detected_at TEXT,
    status TEXT DEFAULT 'open'
);
"""

SEED_HOSTS = [
    (1, "web-01", "10.0.0.10", "Ubuntu 24.04", "web server"),
    (2, "db-01", "10.0.0.20", "Debian 12", "database"),
    (3, "ws-alice", "10.0.1.15", "Windows 11", "workstation"),
    (4, "fw-edge", "10.0.0.1", "pfSense 2.7", "firewall"),
]

SEED_INCIDENTS = [
    (1, 1, "high", "web", "Repeated SQL injection attempts on /login", "2026-09-28T14:02:00Z", "open"),
    (2, 3, "critical", "malware", "Beaconing to 203.0.113.50 every 60s", "2026-09-29T08:41:00Z", "open"),
    (3, 2, "medium", "auth", "Brute-force SSH attempts from 198.51.100.7", "2026-09-30T22:15:00Z", "investigating"),
    (4, 4, "low", "policy", "Outbound DNS to non-corporate resolver", "2026-10-01T10:00:00Z", "closed"),
]


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


def init_db(db_path: Path) -> None:
    """Create the database file and seed sample data if the tables are empty."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.executescript(SEED_SQL)
        if conn.execute("SELECT COUNT(*) FROM hosts").fetchone()[0] == 0:
            conn.executemany("INSERT INTO hosts VALUES (?,?,?,?,?)", SEED_HOSTS)
            conn.executemany("INSERT INTO incidents VALUES (?,?,?,?,?,?,?)", SEED_INCIDENTS)


def list_tables(db_path: Path) -> list[str]:
    """Return the names of all user tables."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    return [r["name"] for r in rows]


def describe_table(db_path: Path, table: str) -> list[dict]:
    """Return column metadata for ``table`` (name interpolated directly into PRAGMA)."""
    with _connect(db_path) as conn:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [
        {"name": r["name"], "type": r["type"], "notnull": bool(r["notnull"]), "pk": bool(r["pk"])}
        for r in rows
    ]


def query(db_path: Path, sql: str, params: list | None = None, max_rows: int = 500) -> dict:
    """Run a statement and return up to ``max_rows`` result rows as dicts."""
    with _connect(db_path) as conn:
        cur = conn.execute(sql, params or [])
        rows = cur.fetchmany(max_rows + 1)
    return {
        "columns": [d[0] for d in cur.description] if cur.description else [],
        "rows": [dict(r) for r in rows[:max_rows]],
        "truncated": len(rows) > max_rows,
    }


def execute(db_path: Path, sql: str) -> dict:
    """Execute one or more statements (``executescript``) and commit."""
    with _connect(db_path) as conn:
        before = conn.total_changes
        conn.executescript(sql)
        changed = conn.total_changes - before
    return {"rows_changed": changed}
