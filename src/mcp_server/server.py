"""Research MCP server served over streamable HTTP with NO auth.

Wraps every toolkit package (files, sqlite_db, http_api, netdiag, security,
memory, commands) as MCP tools, and adds resources, prompts, progress and log
notifications, and elicitation so a capture contains many kinds of JSON-RPC
messages. Guards are intentionally minimal: this server is the subject of
security research. Do not expose it to untrusted networks.

Run:  uv run research-mcp            (or: uv run python -m mcp_server.server)
URL:  http://127.0.0.1:8000/mcp      (override with MCP_HOST / MCP_PORT)
"""

import json
from pathlib import Path

import anyio
import mcp_types
from fastmcp import Context, FastMCP
from mcp_types.version import MODERN_PROTOCOL_VERSIONS

import commands
import files
import http_api
import memory
import netdiag
import security
import sqlite_db
from mcp_server.audit import AuditMiddleware
from mcp_server.config import load_settings

settings = load_settings()
settings.workspace_dir.mkdir(parents=True, exist_ok=True)
sqlite_db.init_db(settings.db_path)
memory.init_store(settings.memory_db_path)
audit = AuditMiddleware(settings.audit_log_path)

WS = settings.workspace_dir
DB = settings.db_path
MEM = settings.memory_db_path

READ_ONLY = {"readOnlyHint": True, "openWorldHint": False}
READ_ONLY_NET = {"readOnlyHint": True, "openWorldHint": True}
WRITES = {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False}
DESTRUCTIVE = {"readOnlyHint": False, "destructiveHint": True, "openWorldHint": False}

mcp = FastMCP(
    "research-mcp",
    instructions=(
        "General-purpose research server: workspace files, a SQLite database of hosts/incidents, "
        "public HTTP APIs, network diagnostics, security utilities, persistent memory and shell commands."
    ),
)
mcp.add_middleware(audit)


CONFIRM_KEY = "confirm"


async def _confirm(ctx: Context, message: str) -> bool | mcp_types.InputRequiredResult:
    """Ask the user to confirm an action, using whichever elicitation flow the client negotiated.

    * Handshake-era protocols: a server-initiated ``elicitation/create`` request
      sent on the open SSE stream (``ctx.elicit``).
    * 2026-07-28 era (SEP-2322, no back-channel): the first round returns an
      ``InputRequiredResult``; the client retries the same ``tools/call`` with
      ``inputResponses``, which this function then reads.

    Returns ``True``/``False`` for the user's decision, or an ``InputRequiredResult``
    the tool must return as-is. If the client cannot elicit at all, the action
    proceeds (minimal guards) and a warning is logged to the client.
    """
    rc = ctx.request_context
    if rc is not None and rc.protocol_version in MODERN_PROTOCOL_VERSIONS:
        responses = ctx.input_responses
        if responses is None or CONFIRM_KEY not in responses:
            schema = {"type": "object", "properties": {"value": {"type": "boolean", "title": "Confirm"}}, "required": ["value"]}
            return mcp_types.InputRequiredResult(
                inputRequests={
                    CONFIRM_KEY: mcp_types.ElicitRequest(
                        params=mcp_types.ElicitRequestFormParams(message=message, requestedSchema=schema)
                    )
                }
            )
        answer = responses[CONFIRM_KEY]
        return getattr(answer, "action", None) == "accept" and bool((getattr(answer, "content", None) or {}).get("value"))
    try:
        result = await ctx.elicit(message, response_type=bool)
    except Exception as exc:
        await ctx.warning(f"Elicitation unavailable ({type(exc).__name__}); proceeding without confirmation.")
        return True
    return result.action == "accept" and bool(result.data)


# --------------------------------------------------------------------------- files

@mcp.tool(annotations=READ_ONLY)
def read_file(path: str, max_bytes: int = 1_000_000) -> dict:
    """Read a text file. Relative paths resolve against the workspace directory."""
    return files.read_file(WS, path, max_bytes)


@mcp.tool(annotations=DESTRUCTIVE)
async def write_file(path: str, content: str, ctx: Context) -> dict | mcp_types.InputRequiredResult:
    """Create or overwrite a text file in the workspace. Asks for confirmation before overwriting."""
    if (WS / path).exists():
        decision = await _confirm(ctx, f"Overwrite existing file '{path}'?")
        if isinstance(decision, mcp_types.InputRequiredResult):
            return decision
        if not decision:
            return {"path": path, "written": False, "reason": "user declined overwrite"}
    return files.write_file(WS, path, content)


@mcp.tool(annotations=WRITES)
def append_file(path: str, content: str) -> dict:
    """Append text to a file in the workspace, creating it if it does not exist."""
    return files.append_file(WS, path, content)


@mcp.tool(annotations=READ_ONLY)
def list_directory(path: str = ".") -> list[dict]:
    """List the entries (name, type, size) of a directory in the workspace."""
    return files.list_dir(WS, path)


@mcp.tool(annotations=READ_ONLY)
def search_files(pattern: str = "*", text: str | None = None, path: str = ".") -> list[dict]:
    """Find files by glob pattern (e.g. '*.txt'), optionally only those containing `text`."""
    return files.search_files(WS, pattern, text, path)


@mcp.tool(annotations=DESTRUCTIVE)
async def delete_file(path: str, ctx: Context) -> str | mcp_types.InputRequiredResult:
    """Delete a file in the workspace after asking the user for confirmation."""
    decision = await _confirm(ctx, f"Delete file '{path}'?")
    if isinstance(decision, mcp_types.InputRequiredResult):
        return decision
    if not decision:
        return "cancelled"
    return "deleted" if files.delete_file(WS, path) else "not found"


# --------------------------------------------------------------------------- sqlite

@mcp.tool(annotations=READ_ONLY)
def db_list_tables() -> list[str]:
    """List the tables in the research SQLite database (seeded with `hosts` and `incidents`)."""
    return sqlite_db.list_tables(DB)


@mcp.tool(annotations=READ_ONLY)
def db_describe_table(table: str) -> list[dict]:
    """Describe the columns of a table in the research database."""
    return sqlite_db.describe_table(DB, table)


@mcp.tool(annotations=READ_ONLY)
def db_query(sql: str, params: list | None = None, max_rows: int = 500) -> dict:
    """Run a SQL query (typically SELECT) with optional positional `?` parameters and return rows."""
    return sqlite_db.query(DB, sql, params, max_rows)


@mcp.tool(annotations=DESTRUCTIVE)
def db_execute(sql: str) -> dict:
    """Execute one or more SQL statements (INSERT/UPDATE/DELETE/DDL) against the research database."""
    return sqlite_db.execute(DB, sql)


# --------------------------------------------------------------------------- http / public APIs

@mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": True})
def http_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | None = None,
    max_chars: int = 20_000,
) -> dict:
    """Send an HTTP request to any URL and return status, headers and the (truncated) body."""
    return http_api.http_request(url, method, headers, body, max_chars)


@mcp.tool(annotations=READ_ONLY_NET)
def get_weather(latitude: float, longitude: float) -> dict:
    """Get the current weather at a coordinate (Open-Meteo)."""
    return http_api.weather(latitude, longitude)


@mcp.tool(annotations=READ_ONLY_NET)
def get_country_info(country_code: str) -> dict:
    """Look up a country's names, region and bordering countries by ISO 3166-1 alpha-2 code, e.g. 'LB' (Nager.Date)."""
    return http_api.country_info(country_code)


@mcp.tool(annotations=READ_ONLY_NET)
def get_wikipedia_summary(title: str, lang: str = "en") -> dict:
    """Get the summary of a Wikipedia article by title."""
    return http_api.wiki_summary(title, lang)


@mcp.tool(annotations=READ_ONLY_NET)
def geolocate_ip(ip: str = "") -> dict:
    """Geolocate an IP address (empty string = this server's public IP) via ip-api.com."""
    return http_api.ip_geolocate(ip)


# --------------------------------------------------------------------------- network diagnostics

@mcp.tool(annotations=READ_ONLY_NET)
def dns_lookup(name: str, record_type: str = "A", nameserver: str | None = None) -> dict:
    """Resolve a DNS name for a record type (A, AAAA, MX, TXT, NS, CNAME, SOA...), optionally via a specific resolver."""
    return netdiag.dns_lookup(name, record_type, nameserver)


@mcp.tool(annotations=READ_ONLY_NET)
def reverse_dns(ip: str) -> dict:
    """Return the PTR (reverse DNS) records for an IP address."""
    return netdiag.reverse_dns(ip)


@mcp.tool(annotations=READ_ONLY_NET)
def tls_certificate(host: str, port: int = 443) -> dict:
    """Connect over TLS and report protocol version, cipher, and certificate subject/issuer/validity/SANs."""
    return netdiag.tls_cert_info(host, port)


@mcp.tool(annotations=READ_ONLY_NET)
def http_security_headers(url: str) -> dict:
    """Fetch a URL's response headers and list missing common security headers."""
    return netdiag.http_headers(url)


@mcp.tool(annotations=READ_ONLY_NET)
async def tcp_port_check(host: str, ports: list[int], ctx: Context, timeout: float = 2.0) -> list[dict]:
    """Check whether TCP ports on a host are open, closed or filtered. Reports progress per port."""
    results = []
    for i, port in enumerate(ports, start=1):
        [result] = await anyio.to_thread.run_sync(netdiag.tcp_port_check, host, [port], timeout)
        results.append(result)
        await ctx.report_progress(i, len(ports), f"{host}:{port} {result['state']}")
    await ctx.info(f"Port check on {host}: {sum(r['state'] == 'open' for r in results)} open of {len(ports)}")
    return results


@mcp.tool(annotations=READ_ONLY_NET)
def rdap_lookup(query: str) -> dict:
    """Look up domain or IP registration data (RDAP, the successor to WHOIS)."""
    return netdiag.rdap_lookup(query)


# --------------------------------------------------------------------------- security utilities

@mcp.tool(annotations=READ_ONLY)
def hash_text(text: str, algorithm: str = "sha256") -> dict:
    """Hash a string with any hashlib algorithm (md5, sha1, sha256, sha512, blake2b, ...)."""
    return security.hash_text(text, algorithm)


@mcp.tool(annotations=READ_ONLY)
def hash_file(path: str, algorithms: list[str] | None = None) -> dict:
    """Hash a file (relative to the workspace) with one or more algorithms (default md5, sha1, sha256)."""
    return security.hash_file(WS / path, algorithms)


@mcp.tool(annotations=READ_ONLY)
def decode_jwt(token: str) -> dict:
    """Decode a JWT's header and payload without verifying its signature."""
    return security.decode_jwt(token)


@mcp.tool(annotations=READ_ONLY)
def encode_decode(data: str, codec: str, direction: str = "encode") -> str:
    """Encode or decode data with codec 'base64', 'base64url', 'hex' or 'url'; direction 'encode' or 'decode'."""
    return security.encode_decode(data, codec, direction)


@mcp.tool(annotations=READ_ONLY_NET)
def check_password_pwned(password: str) -> dict:
    """Check whether a password appears in known breaches (HIBP, k-anonymity: only a 5-char hash prefix is sent)."""
    return security.password_pwned(password)


@mcp.tool(annotations=READ_ONLY_NET)
def lookup_cve(cve_id: str) -> dict:
    """Fetch a CVE's description, CVSS metrics and references (CIRCL CVE search), e.g. 'CVE-2021-44228'."""
    return security.cve_lookup(cve_id)


# --------------------------------------------------------------------------- memory

@mcp.tool(annotations=WRITES)
def remember(key: str, value: str, tags: list[str] | None = None) -> dict:
    """Store a fact in persistent memory under a key (overwrites an existing key). Survives restarts."""
    return memory.remember(MEM, key, value, tags)


@mcp.tool(annotations=READ_ONLY)
def recall(key: str) -> dict | str:
    """Retrieve a fact from persistent memory by key."""
    return memory.recall(MEM, key) or "not found"


@mcp.tool(annotations=READ_ONLY)
def list_memories(tag: str | None = None, contains: str | None = None) -> list[dict]:
    """List stored memories, optionally filtered by tag or substring."""
    return memory.list_memories(MEM, tag, contains)


@mcp.tool(annotations=DESTRUCTIVE)
def forget(key: str) -> str:
    """Delete a fact from persistent memory by key."""
    return "forgotten" if memory.forget(MEM, key) else "not found"


# --------------------------------------------------------------------------- commands

@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "openWorldHint": True})
def run_command(command: str, timeout: float = 30.0) -> dict:
    """Run a shell command on the server (cwd = workspace) and return exit code, stdout and stderr."""
    return commands.run_command(command, timeout, cwd=str(WS))


@mcp.tool(annotations=READ_ONLY_NET)
async def ping_host(host: str, ctx: Context, count: int = 4) -> dict:
    """Ping a host, streaming each reply as a progress/log notification, and return the full output."""
    lines: list[str] = []
    replies = 0
    async for line in commands.stream_command(commands.ping_args(host, count), timeout=count * 3 + 5):
        lines.append(line)
        await ctx.debug(line)
        if "bytes from" in line:
            replies += 1
            await ctx.report_progress(replies, count, line)
    return {"host": host, "sent": count, "received": replies, "output": "\n".join(lines)}


# --------------------------------------------------------------------------- resources

@mcp.resource("workspace://{path*}", mime_type="text/plain")
def workspace_file(path: str) -> str:
    """Contents of a file in the workspace directory."""
    return files.read_file(WS, path)["content"]


@mcp.resource("db://schema", mime_type="application/json")
def db_schema() -> str:
    """Schema of every table in the research database."""
    return json.dumps({t: sqlite_db.describe_table(DB, t) for t in sqlite_db.list_tables(DB)}, indent=2)


@mcp.resource("memory://all", mime_type="application/json")
def all_memories() -> str:
    """Every entry in persistent memory."""
    return json.dumps(memory.list_memories(MEM), indent=2)


@mcp.resource("audit://recent", mime_type="application/json")
def recent_audit() -> str:
    """The 50 most recent audit-log records (MCP messages handled by this server)."""
    return json.dumps(audit.read_recent(50), indent=2)


# --------------------------------------------------------------------------- prompts

@mcp.prompt()
def investigate_domain(domain: str) -> str:
    """Prompt template for a passive reconnaissance pass on a domain."""
    return (
        f"Investigate the domain '{domain}'. Use dns_lookup (A, AAAA, MX, NS, TXT), rdap_lookup, "
        f"tls_certificate and http_security_headers. Summarise ownership, hosting, mail setup, TLS posture "
        f"and missing security headers, then save the report to 'reports/{domain}.md' with write_file."
    )


@mcp.prompt()
def triage_incident(incident_id: int) -> str:
    """Prompt template for triaging an incident from the research database."""
    return (
        f"Triage incident #{incident_id}. Query the incidents and hosts tables with db_query, enrich any IPs "
        f"in the description with reverse_dns, geolocate_ip and rdap_lookup, assess severity, and record "
        f"key findings with remember (tag 'incident-{incident_id}')."
    )


@mcp.prompt()
def summarize_audit_log() -> str:
    """Prompt template asking the model to review the server's own audit log."""
    return (
        "Read the resource audit://recent and summarise which tools were called, how long they took, "
        "which failed, and any calls that look risky (shell commands, file deletes, writes outside the workspace)."
    )


def main() -> None:
    """Entry point: serve the MCP server over streamable HTTP."""
    mcp.run(transport="http", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
