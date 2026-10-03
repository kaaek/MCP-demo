"""Network diagnostics toolkit.

DNS, TLS, HTTP-header, TCP-port and RDAP probes. Each call produces distinct
outbound traffic (UDP/53, TCP/443, raw TCP SYNs, HTTPS to RDAP registries),
which makes the agent's side effects easy to fingerprint in a capture.
"""

from netdiag.diag import (
    dns_lookup,
    http_headers,
    rdap_lookup,
    reverse_dns,
    tcp_port_check,
    tls_cert_info,
)

__all__ = ["dns_lookup", "http_headers", "rdap_lookup", "reverse_dns", "tcp_port_check", "tls_cert_info"]
