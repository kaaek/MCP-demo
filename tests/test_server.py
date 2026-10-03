"""End-to-end tests of the MCP server through FastMCP's in-memory client."""

import json

from fastmcp import Client

from mcp_server.server import audit, mcp

EXPECTED_TOOLS = {
    "read_file", "write_file", "append_file", "list_directory", "search_files", "delete_file",
    "db_list_tables", "db_describe_table", "db_query", "db_execute",
    "http_request", "get_weather", "get_country_info", "get_wikipedia_summary", "geolocate_ip",
    "dns_lookup", "reverse_dns", "tls_certificate", "http_security_headers", "tcp_port_check", "rdap_lookup",
    "hash_text", "hash_file", "decode_jwt", "encode_decode", "check_password_pwned", "lookup_cve",
    "remember", "recall", "list_memories", "forget",
    "run_command", "ping_host",
}


async def test_lists_everything():
    """All tools, resources, templates and prompts are registered."""
    async with Client(mcp) as client:
        assert {t.name for t in await client.list_tools()} == EXPECTED_TOOLS
        assert {str(r.uri) for r in await client.list_resources()} == {"db://schema", "memory://all", "audit://recent"}
        assert [t.uri_template for t in await client.list_resource_templates()] == ["workspace://{path*}"]
        assert {p.name for p in await client.list_prompts()} == {"investigate_domain", "triage_incident", "summarize_audit_log"}


async def test_tool_calls_and_audit():
    """Calling tools works end-to-end and each call lands in the audit log."""
    async with Client(mcp) as client:
        await client.call_tool("write_file", {"path": "notes/hello.txt", "content": "hi"})
        read = await client.call_tool("read_file", {"path": "notes/hello.txt"})
        assert read.data["content"] == "hi"
        rows = await client.call_tool("db_query", {"sql": "SELECT COUNT(*) AS n FROM hosts"})
        assert rows.data["rows"] == [{"n": 4}]
        res = await client.read_resource("workspace://notes/hello.txt")
        assert res[0].text == "hi"
        schema = json.loads((await client.read_resource("db://schema"))[0].text)
        assert set(schema) == {"hosts", "incidents"}
    tools_called = [r.get("tool") for r in audit.read_recent(200) if r["method"] == "tools/call"]
    assert {"write_file", "read_file", "db_query"} <= set(tools_called)


async def test_progress_notifications():
    """tcp_port_check emits one progress notification per port."""
    seen: list[float] = []

    async def on_progress(progress, total, message):
        seen.append(progress)

    async with Client(mcp, progress_handler=on_progress) as client:
        await client.call_tool("tcp_port_check", {"host": "127.0.0.1", "ports": [1, 2, 3], "timeout": 0.5})
    assert seen == [1, 2, 3]


async def test_delete_with_elicitation():
    """delete_file asks for confirmation and respects a decline."""
    async def decline(message, response_type, params, context):
        from fastmcp.client.elicitation import ElicitResult
        return ElicitResult(action="decline")

    async with Client(mcp, elicitation_handler=decline) as client:
        await client.call_tool("write_file", {"path": "keep.txt", "content": "x"})
        out = await client.call_tool("delete_file", {"path": "keep.txt"})
        assert out.data == "cancelled"


async def test_delete_with_elicitation_accept():
    """delete_file deletes the file once the user accepts."""
    async def accept(message, response_type, params, context):
        return {"value": True}

    async with Client(mcp, elicitation_handler=accept) as client:
        await client.call_tool("write_file", {"path": "gone.txt", "content": "x"})
        out = await client.call_tool("delete_file", {"path": "gone.txt"})
        assert out.data == "deleted"
    assert any(r.get("input_required") == ["confirm"] for r in audit.read_recent(200))
