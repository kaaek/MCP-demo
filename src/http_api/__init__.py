"""HTTP / public-API toolkit.

A generic HTTP client (any URL, any method — SSRF surface by design) plus thin
wrappers over key-less public APIs. Fetched content flows back to the agent
verbatim, which also makes this the main indirect-prompt-injection channel.
"""

from http_api.client import country_info, http_request, ip_geolocate, weather, wiki_summary

__all__ = ["country_info", "http_request", "ip_geolocate", "weather", "wiki_summary"]
