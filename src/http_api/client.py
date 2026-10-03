"""Synchronous HTTP helpers built on :mod:`httpx`."""

import httpx

USER_AGENT = "research-mcp/0.1 (academic research)"
TIMEOUT = httpx.Timeout(15.0)


def _client() -> httpx.Client:
    """Return a client with a fixed user agent, timeout and redirect following."""
    return httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, follow_redirects=True)


def http_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | None = None,
    max_chars: int = 20_000,
) -> dict:
    """Send an arbitrary HTTP request and return status, headers and (truncated) body."""
    with _client() as client:
        resp = client.request(method.upper(), url, headers=headers, content=body)
    text = resp.text
    return {
        "url": str(resp.url),
        "status": resp.status_code,
        "headers": dict(resp.headers),
        "elapsed_ms": round(resp.elapsed.total_seconds() * 1000, 1),
        "truncated": len(text) > max_chars,
        "body": text[:max_chars],
    }


def _get_json(url: str, params: dict | None = None) -> dict | list:
    """GET ``url`` and return the decoded JSON body, raising on HTTP errors."""
    with _client() as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def weather(latitude: float, longitude: float) -> dict:
    """Current weather from Open-Meteo (https://open-meteo.com, no key)."""
    data = _get_json(
        "https://api.open-meteo.com/v1/forecast",
        {"latitude": latitude, "longitude": longitude, "current_weather": "true"},
    )
    return {"latitude": latitude, "longitude": longitude, **data.get("current_weather", {})}


def country_info(country_code: str) -> dict:
    """Country names, region and neighbours from Nager.Date (https://date.nager.at, no key)."""
    return _get_json(f"https://date.nager.at/api/v3/CountryInfo/{country_code.upper()}")


def wiki_summary(title: str, lang: str = "en") -> dict:
    """Page summary from the Wikipedia REST API."""
    data = _get_json(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}")
    return {
        "title": data.get("title"),
        "description": data.get("description"),
        "extract": data.get("extract"),
        "url": data.get("content_urls", {}).get("desktop", {}).get("page"),
    }


def ip_geolocate(ip: str = "") -> dict:
    """Geolocate an IP via ip-api.com (plain HTTP, so the exchange is visible in captures)."""
    return _get_json(f"http://ip-api.com/json/{ip}")
