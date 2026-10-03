"""Tests for the security toolkit (offline functions plus marked network checks)."""

import base64
import json

import pytest

from security import cve_lookup, decode_jwt, encode_decode, hash_file, hash_text, password_pwned


def test_hashes(tmp_path):
    """Text and file hashing match known digests."""
    assert hash_text("abc")["hexdigest"].startswith("ba7816bf")
    f = tmp_path / "f"
    f.write_text("abc")
    assert hash_file(f)["md5"] == "900150983cd24fb0d6963f7d28e17f72"


def test_decode_jwt():
    """A hand-built unsigned JWT decodes to its header and payload."""
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    token = f"{enc({'alg': 'none'})}.{enc({'sub': 'alice'})}."
    out = decode_jwt(token)
    assert out["header"] == {"alg": "none"} and out["payload"] == {"sub": "alice"}
    assert out["signature_present"] is False


@pytest.mark.parametrize("codec", ["base64", "base64url", "hex", "url"])
def test_encode_roundtrip(codec):
    """Every codec round-trips a string with special characters."""
    s = "a b/c?d=é"
    assert encode_decode(encode_decode(s, codec), codec, "decode") == s


@pytest.mark.network
def test_password_pwned():
    """'password' is in HIBP."""
    assert password_pwned("password")["pwned"] is True


@pytest.mark.network
def test_cve_lookup():
    """Log4Shell resolves to a published CVE record."""
    assert cve_lookup("CVE-2021-44228")["id"] == "CVE-2021-44228"
