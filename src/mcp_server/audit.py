"""JSONL audit logging middleware.

Writes one line per MCP message handled by the server (requests and
notifications). Each line includes a UTC timestamp, session id, method, tool name
and arguments (for ``tools/call``), duration and response size. This lets the
log be lined up packet-by-packet with a Wireshark/tshark capture.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext


def _payload_size(result: Any) -> int:
    """Approximate the serialized size (bytes) of a handler result."""
    if result is None:
        return 0
    if hasattr(result, "content") and isinstance(result.content, list):
        payload: Any = [b.model_dump(mode="json") if hasattr(b, "model_dump") else b for b in result.content]
    elif hasattr(result, "model_dump"):
        payload = result.model_dump(mode="json")
    else:
        payload = result
    return len(json.dumps(payload, default=str).encode())


class AuditMiddleware(Middleware):
    """FastMCP middleware that appends a JSON record per handled message to a log file."""

    def __init__(self, log_path: Path) -> None:
        """Create the middleware, ensuring the log directory exists."""
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, record: dict) -> None:
        """Append ``record`` as a single JSON line."""
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")

    async def on_message(self, context: MiddlewareContext, call_next):
        """Time the downstream handler and log the outcome, re-raising any error."""
        start = time.perf_counter()
        record: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": context.type,
            "method": context.method,
            "session_id": None,
        }
        try:
            record["session_id"] = context.fastmcp_context.session_id if context.fastmcp_context else None
        except Exception:  # no session bound (e.g. during initialize)
            pass
        if context.method == "tools/call":
            record["tool"] = getattr(context.message, "name", None)
            record["arguments"] = getattr(context.message, "arguments", None)
        elif context.method in ("resources/read", "prompts/get"):
            record["target"] = str(getattr(context.message, "uri", None) or getattr(context.message, "name", None))

        try:
            result = await call_next(context)
        except Exception as exc:
            record.update(duration_ms=round((time.perf_counter() - start) * 1000, 2), error=repr(exc))
            self._write(record)
            raise
        record.update(
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            result_bytes=_payload_size(result),
            is_error=bool(getattr(result, "is_error", False)),
        )
        if getattr(result, "input_required", None) is not None:
            record["input_required"] = list(result.input_required.input_requests or {})
        self._write(record)
        return result

    def read_recent(self, limit: int = 50) -> list[dict]:
        """Return the last ``limit`` audit records (oldest first)."""
        if not self.log_path.exists():
            return []
        lines = self.log_path.read_text(encoding="utf-8").splitlines()[-limit:]
        return [json.loads(line) for line in lines if line.strip()]
