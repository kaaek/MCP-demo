# Test Prompts for research-mcp Tools

One prompt per tool exposed in `src/mcp_server/server.py`.

## Files

### read_file
> Use the `read_file` tool to read `notes/test.txt` from the workspace. Show me its exact contents. (Run after `write_file`.)

**Expect:** returns the file content. A missing path should return a clear error. Also try `max_bytes=5` to verify truncation.

### write_file
> Use the `write_file` tool to create `notes/test.txt` with the content "hello from write_file". Then call it again with the same path and content "overwritten" and tell me what happened.

**Expect:** first call creates the file. Second call triggers a confirmation (elicitation) before overwriting. Decline once to confirm `written: False`, then accept to confirm the overwrite.

### append_file
> Use the `append_file` tool to append the line "\nappended line" to `notes/test.txt`, then to create a brand new file `notes/new.txt` containing "first line".

**Expect:** the existing file gains the extra line; the new file is created.

### list_directory
> Use the `list_directory` tool to list the workspace root, then list the `notes` subdirectory. Report each entry's name, type and size.

**Expect:** entries with name/type/size; `notes` shows `test.txt` and `new.txt`.

### search_files
> Use the `search_files` tool to find all `*.txt` files in the workspace, then search again for `*.txt` files containing the text "appended".

**Expect:** the first call lists both files; the second only `notes/test.txt`.

### delete_file
> Use the `delete_file` tool to delete `notes/new.txt`. Then try to delete `notes/does-not-exist.txt`.

**Expect:** a confirmation prompt, then `deleted`. The second returns `not found` (after confirmation). Declining returns `cancelled`.

## SQLite database

### db_list_tables
> Use the `db_list_tables` tool and tell me which tables exist in the research database.

**Expect:** at least `hosts` and `incidents`.

### db_describe_table
> Use the `db_describe_table` tool on `hosts` and on `incidents`. Summarise the columns and types of each. Then try it on a table called `nonexistent`.

**Expect:** column metadata for both; an error for the unknown table.

### db_query
> Use the `db_query` tool to run `SELECT * FROM hosts WHERE id > ?` with params `[0]` and `max_rows` 3. Tell me how many rows came back and whether the result was truncated.

**Expect:** at most 3 rows. Also try a parameterised query with no params, and an invalid SQL string to check the error.

### db_execute
> Use the `db_execute` tool to create a table `test_items (id INTEGER PRIMARY KEY, name TEXT)`, insert two rows, update one, and finally drop the table. Then use `db_list_tables` to confirm it is gone.

**Expect:** each statement succeeds and reports affected rows; the table is absent at the end.

## HTTP / public APIs

### http_request
> Use the `http_request` tool to GET `https://httpbin.org/get` with the header `X-Test: research` and `max_chars` of 500. Then POST `https://httpbin.org/post` with body `{"a": 1}` and header `Content-Type: application/json`.

**Expect:** status 200, echoed header in the body, truncated body at 500 chars, and the POSTed JSON echoed back.

### get_weather
> Use the `get_weather` tool for Beirut (latitude 33.8938, longitude 35.5018) and report the current temperature and wind speed.

**Expect:** current weather data from Open-Meteo.

### get_country_info
> Use the `get_country_info` tool with country code `LB`. List the official name, region and bordering countries. Then try the invalid code `ZZ`.

**Expect:** Lebanon, with borders Israel and Syria (SY, IL). The invalid code returns an error.

### get_wikipedia_summary
> Use the `get_wikipedia_summary` tool for the title "Model Context Protocol" in English, then for "Liban" with `lang` set to `fr`.

**Expect:** a summary extract for each; a nonexistent title should return a not-found error.

### geolocate_ip
> Use the `geolocate_ip` tool for `8.8.8.8`, then call it again with an empty string to geolocate this server's public IP.

**Expect:** country/city/ISP for Google DNS (US); then the server's own location.

## Network diagnostics

### dns_lookup
> Use the `dns_lookup` tool to resolve the MX and TXT records of `example.com`. Then resolve the A record of `example.com` using the nameserver `1.1.1.1`.

**Expect:** records for each type; the custom resolver is used for the last call.

### reverse_dns
> Use the `reverse_dns` tool on `8.8.8.8` and on `1.1.1.1`.

**Expect:** PTR names `dns.google` and `one.one.one.one`.

### tls_certificate
> Use the `tls_certificate` tool on `example.com` port 443. Report the TLS version, cipher, issuer, subject, validity dates and SANs.

**Expect:** certificate details. Try a host with no TLS (e.g. port 80) to check the error.

### http_security_headers
> Use the `http_security_headers` tool on `https://example.com` and list which common security headers are missing.

**Expect:** the response headers plus a missing-headers list (e.g. HSTS, CSP).

### tcp_port_check
> Use the `tcp_port_check` tool on `scanme.nmap.org` for ports 22, 80, 443 and 9999 with a timeout of 2 seconds. Report each port's state.

**Expect:** per-port `open`/`closed`/`filtered`, with a progress notification per port and an info log summarising open ports. Only scan hosts you are authorised to scan (`scanme.nmap.org` permits this; `127.0.0.1` also works).

### rdap_lookup
> Use the `rdap_lookup` tool on the domain `example.com`, then on the IP `8.8.8.8`. Summarise registrar/owner and registration dates.

**Expect:** RDAP registration data for each.

## Security utilities

### hash_text
> Use the `hash_text` tool to hash "password" with md5, sha256 and blake2b. Then try the algorithm "notahash".

**Expect:** md5 `5f4dcc3b5aa765d61d8327deb882cf99`, sha256 `5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8`; an error for the invalid algorithm.

### hash_file
> Use the `hash_file` tool on `notes/test.txt` with the default algorithms, then again with only `["sha512"]`.

**Expect:** md5/sha1/sha256 first, then only sha512. Also try `../../etc/passwd` to probe path-traversal behaviour (a security-research check).

### decode_jwt
> Use the `decode_jwt` tool on this token and show the header and payload: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c`

**Expect:** header `{"alg":"HS256","typ":"JWT"}`, payload with `sub` 1234567890, `name` John Doe, `iat` 1516239022. A malformed token returns an error.

### encode_decode
> Use the `encode_decode` tool to base64-encode "research-mcp", then decode the result back. Then hex-encode "hi", and URL-encode "a b&c=d".

**Expect:** `cmVzZWFyY2gtbWNw` and round trip; `6869`; `a%20b%26c%3Dd`. An unknown codec returns an error.

### check_password_pwned
> Use the `check_password_pwned` tool on the password "password123" and tell me whether and how many times it appears in breaches. Only use throwaway test passwords.

**Expect:** found with a large count; only a 5-char hash prefix leaves the server.

### lookup_cve
> Use the `lookup_cve` tool for `CVE-2021-44228` and summarise the description, CVSS score and first three references. Then try `CVE-0000-0000`.

**Expect:** Log4Shell details with critical CVSS (10.0); an error/not-found for the fake ID.

## Memory

### remember
> Use the `remember` tool to store key `test_fact` with value "the sky is blue" and tags `["test", "demo"]`. Then store the same key with value "the sky is grey" to overwrite it.

**Expect:** stored, then overwritten under the same key.

### recall
> Use the `recall` tool for the key `test_fact`, then for `missing_key`.

**Expect:** the latest value ("the sky is grey") and tags; `not found` for the missing key.

### list_memories
> Use the `list_memories` tool with no filters, then filtered by tag `demo`, then with `contains` set to "grey".

**Expect:** all entries; then only matching ones (`test_fact`).

### forget
> Use the `forget` tool to delete `test_fact`, then call it again on the same key. Confirm with `recall`.

**Expect:** `forgotten`, then `not found`.

## Commands

### run_command
> Use the `run_command` tool to run `pwd && ls -la` and show the exit code, stdout and stderr. Then run `ls /nonexistent` and `sleep 5` with a timeout of 1 second.

**Expect:** cwd is the workspace with exit 0; non-zero exit and stderr for the bad path; a timeout error for the sleep.

### ping_host
> Use the `ping_host` tool on `127.0.0.1` with a count of 3. Report sent, received and the full output.

**Expect:** sent 3, received 3, with a progress notification and a debug log per reply. Also try an unreachable host (e.g. `192.0.2.1`) for received 0.

## Cross-tool scenarios (optional)

- **Round trip:** `write_file` -> `hash_file` -> `hash_text` on the same content; the sha256 values should match.
- **Memory + DB:** `db_query` on `incidents` -> `remember` the key findings -> `list_memories` with the matching tag.
- **Elicitation:** repeat `write_file` (overwrite) and `delete_file` on both a handshake-era client and a 2026-07-28 client to exercise both `_confirm` flows.
