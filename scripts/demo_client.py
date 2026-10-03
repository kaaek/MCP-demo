"""Demo MCP client that exercises one tool per toolkit over streamable HTTP.

Useful for producing a reproducible capture:

    uv run research-mcp &                                  # start the server
    tshark -i lo -f "tcp port 8000" -w captures/demo.pcapng &
    uv run python scripts/demo_client.py [URL]

URL defaults to http://127.0.0.1:8000/mcp.
"""

import asyncio
import sys

from fastmcp import Client

CALLS = [
    ("write_file", {"path": "demo/hello.txt", "content": "hello from the demo client\n"}),
    ("read_file", {"path": "demo/hello.txt"}),
    ("db_query", {"sql": "SELECT id, severity, description FROM incidents WHERE status != 'closed'"}),
    ("dns_lookup", {"name": "example.com", "record_type": "A"}),
    ("tcp_port_check", {"host": "127.0.0.1", "ports": [22, 80, 8000]}),
    ("hash_text", {"text": "research", "algorithm": "sha256"}),
    ("remember", {"key": "demo", "value": "demo client ran", "tags": ["demo"]}),
    ("run_command", {"command": "uname -a"}),
    ("delete_file", {"path": "demo/hello.txt"}),
]


async def main(url: str) -> None:
    """Connect, list capabilities, call each demo tool, then read a resource and a prompt."""

    async def on_progress(progress, total, message):
        print(f"    progress {progress}/{total}: {message}")

    async def on_elicit(message, response_type, params, context):
        print(f"    elicitation: {message!r} -> accept")
        return {"value": True}

    async with Client(url, progress_handler=on_progress, elicitation_handler=on_elicit) as client:
        tools = await client.list_tools()
        print(f"{len(tools)} tools available")
        for name, args in CALLS:
            print(f"-> {name}({args})")
            result = await client.call_tool(name, args, raise_on_error=False)
            preview = str(result.data if result.data is not None else result.content)[:160]
            print(f"   {'ERROR ' if result.is_error else ''}{preview}")
        schema = await client.read_resource("db://schema")
        print(f"db://schema -> {len(schema[0].text)} chars")
        prompt = await client.get_prompt("investigate_domain", {"domain": "example.com"})
        print(f"prompt investigate_domain -> {prompt.messages[0].content.text[:80]}...")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/mcp"))
