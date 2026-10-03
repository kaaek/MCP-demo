"""Command-execution toolkit.

Runs arbitrary shell commands (no allowlist — minimal guards) and a streaming
``ping`` helper. This is the highest-risk capability on the server and the
main surface for command-injection experiments.
"""

from commands.runner import ping_args, run_command, stream_command

__all__ = ["ping_args", "run_command", "stream_command"]
