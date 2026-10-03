"""Network probing helpers built on the standard library, dnspython and httpx."""

import ipaddress
import socket
import ssl
import time
from collections.abc import Iterator

import dns.resolver
import dns.reversename
import httpx

from http_api.client import USER_AGENT


def dns_lookup(name: str, record_type: str = "A", nameserver: str | None = None) -> dict:
    """Resolve ``name`` for ``record_type`` (A, AAAA, MX, TXT, NS, CNAME, SOA, ...)."""
    resolver = dns.resolver.Resolver()
    if nameserver:
        resolver.nameservers = [nameserver]
    answer = resolver.resolve(name, record_type.upper(), raise_on_no_answer=False)
    return {
        "name": name,
        "type": record_type.upper(),
        "nameserver": answer.nameserver,
        "ttl": answer.rrset.ttl if answer.rrset else None,
        "records": [r.to_text() for r in answer] if answer.rrset else [],
    }


def reverse_dns(ip: str) -> dict:
    """Return the PTR record(s) for an IPv4/IPv6 address."""
    rev = dns.reversename.from_address(ip)
    try:
        records = [r.to_text() for r in dns.resolver.resolve(rev, "PTR")]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        records = []
    return {"ip": ip, "ptr": records}


def tls_cert_info(host: str, port: int = 443) -> dict:
    """Open a TLS connection and return the negotiated protocol, cipher and peer certificate."""
    ctx = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=10) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            cert = tls.getpeercert()
            return {
                "host": host,
                "port": port,
                "tls_version": tls.version(),
                "cipher": tls.cipher()[0],
                "subject": dict(x[0] for x in cert.get("subject", ())),
                "issuer": dict(x[0] for x in cert.get("issuer", ())),
                "not_before": cert.get("notBefore"),
                "not_after": cert.get("notAfter"),
                "san": [v for _, v in cert.get("subjectAltName", ())],
            }


def http_headers(url: str) -> dict:
    """Fetch only the response headers (HEAD, falling back to GET) and flag missing security headers."""
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=10, follow_redirects=True) as client:
        resp = client.head(url)
        if resp.status_code == 405:
            resp = client.get(url)
    headers = {k.lower(): v for k, v in resp.headers.items()}
    wanted = [
        "strict-transport-security",
        "content-security-policy",
        "x-content-type-options",
        "x-frame-options",
        "referrer-policy",
    ]
    return {
        "url": str(resp.url),
        "status": resp.status_code,
        "headers": headers,
        "missing_security_headers": [h for h in wanted if h not in headers],
    }


def iter_tcp_port_check(host: str, ports: list[int], timeout: float = 2.0) -> Iterator[dict]:
    """Yield one result per port as each TCP connect attempt finishes."""
    for port in ports:
        start = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                state = "open"
        except TimeoutError:
            state = "filtered"
        except ConnectionRefusedError:
            state = "closed"
        except OSError as exc:
            state = f"error: {exc.strerror or exc}"
        yield {"port": port, "state": state, "rtt_ms": round((time.perf_counter() - start) * 1000, 1)}


def tcp_port_check(host: str, ports: list[int], timeout: float = 2.0) -> list[dict]:
    """Attempt a TCP connect to each port on ``host`` and report open/closed/filtered."""
    return list(iter_tcp_port_check(host, ports, timeout))


def rdap_lookup(query: str) -> dict:
    """Registration data (RDAP) for a domain or IP via the rdap.org bootstrap redirector."""
    try:
        ipaddress.ip_address(query)
        url = f"https://rdap.org/ip/{query}"
    except ValueError:
        url = f"https://rdap.org/domain/{query}"
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=15, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
    return {
        "query": query,
        "source": str(resp.url),
        "handle": data.get("handle"),
        "name": data.get("name") or data.get("ldhName"),
        "status": data.get("status"),
        "events": [{"action": e.get("eventAction"), "date": e.get("eventDate")} for e in data.get("events", [])],
        "nameservers": [ns.get("ldhName") for ns in data.get("nameservers", [])],
        "country": data.get("country"),
        "cidr": data.get("cidr0_cidrs"),
    }
