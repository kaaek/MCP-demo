"""File operations relative to a workspace directory.

Every function takes the workspace root explicitly so the module stays free of
global state and is easy to test. No confinement check is applied: relative
paths are joined to the workspace and absolute paths are used as-is.
"""

from pathlib import Path


def _resolve(workspace: Path, path: str) -> Path:
    """Join ``path`` to ``workspace`` (absolute paths override the workspace)."""
    return (workspace / path).resolve()


def read_file(workspace: Path, path: str, max_bytes: int = 1_000_000) -> dict:
    """Read a text file and return its content (truncated to ``max_bytes``)."""
    target = _resolve(workspace, path)
    data = target.read_bytes()
    return {
        "path": str(target),
        "size": len(data),
        "truncated": len(data) > max_bytes,
        "content": data[:max_bytes].decode("utf-8", errors="replace"),
    }


def write_file(workspace: Path, path: str, content: str) -> dict:
    """Create or overwrite a text file, creating parent directories as needed."""
    target = _resolve(workspace, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    existed = target.exists()
    target.write_text(content, encoding="utf-8")
    return {"path": str(target), "bytes_written": len(content.encode()), "overwritten": existed}


def append_file(workspace: Path, path: str, content: str) -> dict:
    """Append text to a file, creating it if missing."""
    target = _resolve(workspace, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(content)
    return {"path": str(target), "bytes_appended": len(content.encode()), "size": target.stat().st_size}


def list_dir(workspace: Path, path: str = ".") -> list[dict]:
    """List directory entries with their type and size."""
    target = _resolve(workspace, path)
    return [
        {
            "name": entry.name,
            "type": "dir" if entry.is_dir() else "file",
            "size": entry.stat().st_size if entry.is_file() else None,
        }
        for entry in sorted(target.iterdir())
    ]


def search_files(workspace: Path, pattern: str, text: str | None = None, path: str = ".") -> list[dict]:
    """Find files matching a glob ``pattern``; optionally keep only those containing ``text``.

    Returns at most 200 matches. When ``text`` is given, each match includes the
    line numbers where it occurs.
    """
    root = _resolve(workspace, path)
    results: list[dict] = []
    for match in root.rglob(pattern):
        if not match.is_file():
            continue
        entry: dict = {"path": str(match.relative_to(root))}
        if text is not None:
            try:
                lines = match.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            hits = [i + 1 for i, line in enumerate(lines) if text in line]
            if not hits:
                continue
            entry["lines"] = hits[:50]
        results.append(entry)
        if len(results) >= 200:
            break
    return results


def delete_file(workspace: Path, path: str) -> bool:
    """Delete a file. Returns ``True`` if it existed, ``False`` otherwise."""
    target = _resolve(workspace, path)
    if not target.exists():
        return False
    target.unlink()
    return True
