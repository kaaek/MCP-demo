"""Hashing, encoding, JWT inspection and threat-intel lookups."""

import base64
import binascii
import hashlib
import json
import urllib.parse
from pathlib import Path

import httpx

from http_api.client import USER_AGENT


def hash_text(text: str, algorithm: str = "sha256") -> dict:
    """Hash UTF-8 ``text`` with any :mod:`hashlib` algorithm."""
    return {"algorithm": algorithm, "hexdigest": hashlib.new(algorithm, text.encode()).hexdigest()}


def hash_file(path: Path, algorithms: list[str] | None = None) -> dict:
    """Hash a file with several algorithms in a single streaming pass."""
    hashers = {a: hashlib.new(a) for a in (algorithms or ["md5", "sha1", "sha256"])}
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            for h in hashers.values():
                h.update(chunk)
    return {"path": str(path), "size": path.stat().st_size, **{a: h.hexdigest() for a, h in hashers.items()}}


def _b64url_decode(segment: str) -> bytes:
    """Decode a base64url segment, restoring missing padding."""
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def decode_jwt(token: str) -> dict:
    """Decode a JWT's header and payload WITHOUT verifying the signature."""
    parts = token.strip().split(".")
    if len(parts) < 2:
        raise ValueError("not a JWT: expected at least header.payload")
    return {
        "header": json.loads(_b64url_decode(parts[0])),
        "payload": json.loads(_b64url_decode(parts[1])),
        "signature_present": len(parts) > 2 and bool(parts[2]),
        "verified": False,
    }


def encode_decode(data: str, codec: str, direction: str = "encode") -> str:
    """Encode or decode ``data`` using ``base64``, ``base64url``, ``hex`` or ``url``."""
    codec, encode = codec.lower(), direction.lower() == "encode"
    if codec == "base64":
        return base64.b64encode(data.encode()).decode() if encode else base64.b64decode(data).decode(errors="replace")
    if codec == "base64url":
        return base64.urlsafe_b64encode(data.encode()).decode() if encode else _b64url_decode(data).decode(errors="replace")
    if codec == "hex":
        return data.encode().hex() if encode else binascii.unhexlify(data).decode(errors="replace")
    if codec == "url":
        return urllib.parse.quote(data, safe="") if encode else urllib.parse.unquote(data)
    raise ValueError(f"unsupported codec: {codec}")


def password_pwned(password: str) -> dict:
    """Check a password against HIBP Pwned Passwords using k-anonymity.

    Only the first 5 hex chars of the SHA-1 hash leave the machine.
    """
    digest = hashlib.sha1(password.encode()).hexdigest().upper()
    prefix, suffix = digest[:5], digest[5:]
    resp = httpx.get(
        f"https://api.pwnedpasswords.com/range/{prefix}",
        headers={"User-Agent": USER_AGENT, "Add-Padding": "true"},
        timeout=15,
    )
    resp.raise_for_status()
    count = 0
    for line in resp.text.splitlines():
        candidate, _, n = line.partition(":")
        if candidate == suffix:
            count = int(n)
            break
    return {"sha1_prefix": prefix, "pwned": count > 0, "count": count}


def cve_lookup(cve_id: str) -> dict:
    """Fetch a CVE record from the CIRCL CVE search API (https://cve.circl.lu)."""
    resp = httpx.get(
        f"https://cve.circl.lu/api/cve/{cve_id.upper()}",
        headers={"User-Agent": USER_AGENT},
        timeout=20,
        follow_redirects=True,
    )
    resp.raise_for_status()
    data = resp.json() or {}
    cna = data.get("containers", {}).get("cna", {})
    descriptions = [d.get("value") for d in cna.get("descriptions", []) if d.get("lang", "").startswith("en")]
    metrics = []
    for m in cna.get("metrics", []):
        for key, val in m.items():
            if key.startswith("cvss"):
                metrics.append({"version": key, "score": val.get("baseScore"), "severity": val.get("baseSeverity")})
    return {
        "id": data.get("cveMetadata", {}).get("cveId", cve_id.upper()),
        "state": data.get("cveMetadata", {}).get("state"),
        "published": data.get("cveMetadata", {}).get("datePublished"),
        "title": cna.get("title"),
        "description": descriptions[0] if descriptions else None,
        "metrics": metrics,
        "references": [r.get("url") for r in cna.get("references", [])][:20],
    }
