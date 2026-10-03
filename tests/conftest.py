"""Shared pytest configuration.

Points every server path at a throwaway temp directory *before* the server
module is imported, so tests never touch ./workspace, ./data or ./logs.
"""

import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="research-mcp-tests-"))
os.environ.setdefault("WORKSPACE_DIR", str(_TMP / "workspace"))
os.environ.setdefault("DB_PATH", str(_TMP / "data" / "research.db"))
os.environ.setdefault("MEMORY_DB", str(_TMP / "data" / "memory.db"))
os.environ.setdefault("AUDIT_LOG", str(_TMP / "logs" / "audit.jsonl"))


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A fresh, empty workspace directory for toolkit-level tests."""
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws
