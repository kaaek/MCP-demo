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
    """Run ``command`` through the shell and capture exit code, stdout and stderr."""
    try:
        proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        exit_code, timed_out, out, err = proc.returncode, False, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        exit_code, timed_out, out, err = None, True, exc.stdout, exc.stderr
    return {
        "command": command,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "stdout": _text(out)[:max_chars],
        "stderr": _text(err)[:max_chars],
    }


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
