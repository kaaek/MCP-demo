"""Tests for the files toolkit."""

from files import append_file, delete_file, list_dir, read_file, search_files, write_file


def test_write_read_append(workspace):
    """Writing, appending and reading round-trips content and reports overwrite."""
    assert write_file(workspace, "a/b.txt", "hello\n")["overwritten"] is False
    append_file(workspace, "a/b.txt", "world\n")
    assert read_file(workspace, "a/b.txt")["content"] == "hello\nworld\n"
    assert write_file(workspace, "a/b.txt", "x")["overwritten"] is True


def test_list_search_delete(workspace):
    """Listing, content search and deletion behave as documented."""
    write_file(workspace, "one.txt", "needle here")
    write_file(workspace, "two.log", "nothing")
    assert {e["name"] for e in list_dir(workspace)} == {"one.txt", "two.log"}
    assert search_files(workspace, "*", text="needle") == [{"path": "one.txt", "lines": [1]}]
    assert delete_file(workspace, "one.txt") is True
    assert delete_file(workspace, "one.txt") is False


def test_path_traversal_is_not_blocked(workspace):
    """Minimal guards: relative paths may escape the workspace."""
    write_file(workspace.parent, "outside.txt", "secret")
    assert read_file(workspace, "../outside.txt")["content"] == "secret"
