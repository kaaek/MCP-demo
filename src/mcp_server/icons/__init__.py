"""SVG icons for the server and its tools, embedded as data URIs (MCP ``icons`` field)."""

import base64
from functools import cache
from pathlib import Path

import mcp_types

ICON_DIR = Path(__file__).parent


@cache
def svg_icon(name: str) -> list[mcp_types.Icon]:
    """Return an ``icons`` list holding ``<name>.svg`` as a base64 data URI."""
    data = base64.b64encode((ICON_DIR / f"{name}.svg").read_bytes()).decode()
    return [mcp_types.Icon(src=f"data:image/svg+xml;base64,{data}", mime_type="image/svg+xml", sizes=["any"])]
