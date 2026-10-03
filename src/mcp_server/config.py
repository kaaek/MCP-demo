"""Runtime configuration for the research MCP server.

All settings are read from environment variables so that experiments can be
reproduced by changing the environment only. Paths are resolved relative to
the current working directory unless given as absolute paths.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Immutable bundle of server settings resolved from the environment."""

    host: str
    port: int
    workspace_dir: Path
    db_path: Path
    memory_db_path: Path
    audit_log_path: Path


def load_settings() -> Settings:
    """Build a :class:`Settings` instance from environment variables.

    Variables (defaults in parentheses):
        MCP_HOST (127.0.0.1), MCP_PORT (8000), WORKSPACE_DIR (./workspace),
        DB_PATH (./data/research.db), MEMORY_DB (./data/memory.db),
        AUDIT_LOG (./logs/audit.jsonl).
    """
    return Settings(
        host=os.environ.get("MCP_HOST", "127.0.0.1"),
        port=int(os.environ.get("MCP_PORT", "8000")),
        workspace_dir=Path(os.environ.get("WORKSPACE_DIR", "workspace")).resolve(),
        db_path=Path(os.environ.get("DB_PATH", "data/research.db")).resolve(),
        memory_db_path=Path(os.environ.get("MEMORY_DB", "data/memory.db")).resolve(),
        audit_log_path=Path(os.environ.get("AUDIT_LOG", "logs/audit.jsonl")).resolve(),
    )
