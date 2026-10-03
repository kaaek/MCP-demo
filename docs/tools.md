# Tool catalogue

All tools carry MCP `annotations` (`readOnlyHint`, `destructiveHint`,
`openWorldHint`), so the hints the client sees can be compared with what each
tool actually does.

## Tools

| Tool | Toolkit | Side effects / traffic | Attack surface (minimal guards) |
|---|---|---|---|
| `read_file` | files | local disk read | path traversal / absolute paths |
| `write_file` | files | disk write; **elicitation** before overwrite | arbitrary file write |
| `append_file` | files | disk write | arbitrary file write |
| `list_directory` | files | local | directory enumeration outside workspace |
| `search_files` | files | local | content discovery |
| `delete_file` | files | disk delete; **elicitation** first | arbitrary delete (confirmation bypass if client can't elicit) |
| `db_list_tables` / `db_describe_table` | sqlite_db | local | `describe_table` interpolates the table name into PRAGMA |
| `db_query` | sqlite_db | local | raw SQL (marked read-only, but not enforced) |
| `db_execute` | sqlite_db | local | multi-statement SQL, DDL, `ATTACH DATABASE` |
| `http_request` | http_api | HTTP(S) to any host | SSRF (incl. localhost/metadata IPs), indirect prompt injection via body |
| `get_weather` | http_api | HTTPS → api.open-meteo.com | — |
| `get_country_info` | http_api | HTTPS → date.nager.at | — |
| `get_wikipedia_summary` | http_api | HTTPS → *.wikipedia.org | indirect prompt injection via article text |
| `geolocate_ip` | http_api | **plain HTTP** → ip-api.com (visible in capture) | leaks queried IP in clear |
| `dns_lookup` | netdiag | UDP/53 to system or **chosen** resolver | DNS exfiltration via crafted names |
| `reverse_dns` | netdiag | UDP/53 PTR | — |
| `tls_certificate` | netdiag | TCP+TLS handshake to any host:port | internal service probing |
| `http_security_headers` | netdiag | HEAD/GET to any URL | SSRF |
| `tcp_port_check` | netdiag | TCP SYNs; **progress notifications (SSE)** + log | port scanning |
| `rdap_lookup` | netdiag | HTTPS → rdap.org (+ redirects to registries) | — |
| `hash_text` / `hash_file` | security | local (file read for `hash_file`) | file read outside workspace |
| `decode_jwt` | security | local | — (explicitly unverified) |
| `encode_decode` | security | local | obfuscation helper for payloads |
| `check_password_pwned` | security | HTTPS → api.pwnedpasswords.com (5-char SHA-1 prefix) | secret passes through the MCP channel in clear |
| `lookup_cve` | security | HTTPS → cve.circl.lu | — |
| `remember` / `recall` / `list_memories` / `forget` | memory | local SQLite, persists across sessions | memory poisoning, cross-session injection |
| `run_command` | commands | anything (shell, cwd = workspace) | arbitrary command execution |
| `ping_host` | commands | ICMP; **progress + debug log per reply** | argv-only (no shell), host is user-controlled |

## Resources

- `workspace://{path*}`: contents of a workspace file (template)
- `db://schema`: JSON schema of every table
- `memory://all`: all persistent memories
- `audit://recent`: the last 50 audit records

## Prompts

- `investigate_domain(domain)`: passive recon chain (DNS → RDAP → TLS → headers → write report)
- `triage_incident(incident_id)`: DB query → IP enrichment → `remember`
- `summarize_audit_log()`: the model reviews the server's own audit log

## Protocol notes (observed with FastMCP 4.0 / MCP 2026-07-28)

- The client opens with `server/discover` instead of `initialize`. Every POST
  carries the `mcp-protocol-version` and `mcp-method` headers.
- Responses are `application/json` unless the tool sends notifications
  (progress or logging). Those responses become `text/event-stream`.
- Server-initiated elicitation is gone (SEP-2322). `write_file` and `delete_file`
  return an `InputRequiredResult`, and the client retries the same `tools/call`
  with `inputResponses`. Expect two POSTs for one logical call. Clients on older
  protocol versions still get a classic `elicitation/create` request over SSE.
- The logging capability is deprecated in this revision (SEP-2577), but it
  still works.
