"""Tests for http_api, netdiag and commands toolkits.

Tests needing internet access are marked ``network``; run offline with
``pytest -m 'not network'``.
"""

import socket

import pytest

from commands import run_command, stream_command
from http_api import country_info, http_request
from netdiag import dns_lookup, http_headers, tcp_port_check, tls_cert_info


def test_tcp_port_check_local():
    """A listening local socket reports open; a freshly freed port reports closed."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen()
    open_port = srv.getsockname()[1]
    tmp = socket.socket()
    tmp.bind(("127.0.0.1", 0))
    closed_port = tmp.getsockname()[1]
    tmp.close()
    try:
        states = {r["port"]: r["state"] for r in tcp_port_check("127.0.0.1", [open_port, closed_port])}
    finally:
        srv.close()
    assert states == {open_port: "open", closed_port: "closed"}


def test_run_command():
    """Shell commands run with exit code and output captured; timeouts are reported."""
    out = run_command("echo hi && exit 3")
    assert out["stdout"].strip() == "hi" and out["exit_code"] == 3
    assert run_command("sleep 5", timeout=0.5)["timed_out"] is True


async def test_stream_command():
    """stream_command yields lines in order."""
    lines = [line async for line in stream_command(["printf", "a\\nb\\n"])]
    assert lines == ["a", "b"]


@pytest.mark.network
def test_dns_and_tls():
    """Public DNS and TLS probes return sensible data."""
    assert dns_lookup("example.com")["records"]
    assert tls_cert_info("example.com")["tls_version"].startswith("TLS")


@pytest.mark.network
def test_http():
    """Generic HTTP, security-header check and a public API wrapper work."""
    assert http_request("https://example.com")["status"] == 200
    assert "status" in http_headers("https://example.com")
    assert country_info("lb")["commonName"] == "Lebanon"
