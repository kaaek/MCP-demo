"""Shell command execution via :mod:`subprocess` and :mod:`asyncio`."""

import asyncio
import subprocess
from collections.abc import AsyncIterator


def _text(value: str | bytes | None) -> str:
    """Normalise subprocess output (which may be bytes after a timeout) to text."""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value or ""


def run_command(command: str, timeout: float = 30.0, cwd: str | None = None, max_chars: int = 50_000) -> dict:
    """Run ``command`` through the shell and capture exit code, stdout and stderr.

    Raises ``RuntimeError`` on a non-zero exit (including a missing binary, exit 127)
    and ``TimeoutError`` if the command outlives ``timeout``.
    """
    try:
        proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(
            f"command timed out after {timeout}s: {command}\n"
            f"stdout: {_text(exc.stdout)[:max_chars]}\nstderr: {_text(exc.stderr)[:max_chars]}"
        ) from exc
    out, err = _text(proc.stdout)[:max_chars], _text(proc.stderr)[:max_chars]
    if proc.returncode != 0:
        raise RuntimeError(
            f"command exited with code {proc.returncode}: {command}\nstdout: {out}\nstderr: {err}"
        )
    return {"command": command, "exit_code": 0, "stdout": out, "stderr": err}


async def stream_command(args: list[str], timeout: float = 60.0) -> AsyncIterator[str]:
    """Run ``args`` (no shell) and yield combined stdout/stderr lines as they arrive.

    The process is killed if it outlives ``timeout`` seconds or the caller stops early.
    """
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    assert proc.stdout is not None
    try:
        async with asyncio.timeout(timeout):
            async for raw in proc.stdout:
                yield raw.decode(errors="replace").rstrip("\n")
            await proc.wait()
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()


def ping_args(host: str, count: int = 4) -> list[str]:
    """Build the ``ping`` argv for ``count`` echo requests to ``host``."""
    return ["ping", "-c", str(count), "-W", "2", host]
