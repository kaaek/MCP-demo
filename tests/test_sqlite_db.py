"""Tests for the sqlite_db toolkit."""

from sqlite_db import describe_table, execute, init_db, list_tables, query


def test_seed_and_query(tmp_path):
    """The seeded database has hosts/incidents and supports parameterised queries."""
    db = tmp_path / "t.db"
    init_db(db)
    init_db(db)  # idempotent
    assert list_tables(db) == ["hosts", "incidents"]
    assert any(c["name"] == "hostname" for c in describe_table(db, "hosts"))
    res = query(db, "SELECT hostname FROM hosts WHERE id = ?", [1])
    assert res["rows"] == [{"hostname": "web-01"}]


def test_execute_and_truncation(tmp_path):
    """execute() reports changed rows; query() truncates at max_rows."""
    db = tmp_path / "t.db"
    init_db(db)
    assert execute(db, "UPDATE incidents SET status='closed'")["rows_changed"] == 4
    res = query(db, "SELECT * FROM incidents", max_rows=2)
    assert len(res["rows"]) == 2 and res["truncated"] is True
