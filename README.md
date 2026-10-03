# research-mcp

A general-purpose [MCP](https://modelcontextprotocol.io) server built with
[FastMCP](https://gofastmcp.com). It is served over **streamable HTTP with no
authentication or TLS**. The server is the **subject of study** for network-level
(Wireshark/tshark) and security research. Its tools are chosen to produce varied
agent behaviour and varied traffic, and its guards are deliberately **minimal**.

> ⚠️ It runs arbitrary shell commands, reads and writes any path, executes raw SQL
> and fetches any URL. It binds to `127.0.0.1` by default. Do not expose it to
> untrusted networks.

## Setup

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # if uv is missing
uv sync                                           # creates .venv and installs deps + dev deps
```

## Run

```bash
uv run research-mcp                 # → http://127.0.0.1:8000/mcp
MCP_HOST=0.0.0.0 MCP_PORT=9000 uv run research-mcp
```

| Variable        | Default              | Purpose                                   |
|-----------------|----------------------|-------------------------------------------|
| `MCP_HOST`      | `127.0.0.1`          | Bind address                              |
| `MCP_PORT`      | `8000`               | Port                                      |
| `WORKSPACE_DIR` | `./workspace`        | Base dir for file tools / `run_command` cwd |
| `DB_PATH`       | `./data/research.db` | SQLite DB (seeded with hosts/incidents)   |
| `MEMORY_DB`     | `./data/memory.db`   | Persistent memory store                   |
| `AUDIT_LOG`     | `./logs/audit.jsonl` | One JSON line per MCP message handled     |

### Connecting a client

Use any client that supports streamable HTTP and point it at
`http://127.0.0.1:8000/mcp`. Examples:

- Claude Code: `claude mcp add --transport http research http://127.0.0.1:8000/mcp`
- MCP Inspector: `npx @modelcontextprotocol/inspector`, then choose *Streamable HTTP*.
- `uv run python scripts/demo_client.py` runs a scripted call to one tool from each toolkit.

## Capturing traffic

```bash
uv run research-mcp &
tshark -i lo -f "tcp port 8000" -w captures/run.pcapng &     # client ↔ server
tshark -i any -f "not port 8000" -w captures/egress.pcapng & # server side effects (DNS, HTTPS, ...)
uv run python scripts/demo_client.py
```

Useful display filters: `http.request.method == "POST"`, `http.content_type contains "event-stream"`,
`http.request.line contains "mcp-method"`, `dns`, `tls.handshake.extensions_server_name`.

Match packets against `logs/audit.jsonl` using the `ts`, `method` and `tool`
fields. Note that on the `2026-07-28` protocol the `session_id` field changes
with every request.

## Layout

```
src/
  mcp_server/   FastMCP app (server.py), config, JSONL audit middleware
  files/        workspace file operations
  sqlite_db/    SQLite access + seeded sample data
  http_api/     generic HTTP client + key-less public APIs
  netdiag/      DNS, reverse DNS, TLS, HTTP headers, TCP ports, RDAP
  security/     hashing, encoders, JWT decode, HIBP, CVE lookup
  memory/       persistent key/value memory
  commands/     shell execution + streaming ping
tests/          pytest suite (network tests marked `network`)
scripts/        demo_client.py traffic generator
docs/tools.md   tool catalogue with the attack surface each tool exposes
```

The toolkit packages are plain Python and do not import MCP.
`src/mcp_server/server.py` wraps them with `@mcp.tool()`.

## Tests

```bash
uv run pytest                 # everything
uv run pytest -m "not network"  # offline only
```
