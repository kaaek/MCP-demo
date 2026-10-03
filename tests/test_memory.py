"""Tests for the memory toolkit."""

from memory import forget, init_store, list_memories, recall, remember


def test_memory_lifecycle(tmp_path):
    """Remember, filter, recall and forget a memory entry."""
    db = tmp_path / "m.db"
    init_store(db)
    remember(db, "c2", "203.0.113.50 is a C2 server", ["ioc", "incident-2"])
    remember(db, "note", "unrelated")
    assert recall(db, "c2")["tags"] == ["ioc", "incident-2"]
    assert [m["key"] for m in list_memories(db, tag="ioc")] == ["c2"]
    assert [m["key"] for m in list_memories(db, contains="unrel")] == ["note"]
    assert forget(db, "c2") is True and recall(db, "c2") is None
