"""Shared outbound HTTP: one configured client + SSRF guard.

Every adapter that touches user-supplied URLs must pass them through
`ensure_public_url` — private/loopback/link-local targets are refused.
"""

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

USER_AGENT = "ForgeBot/0.1 (+https://github.com/rudiselbrett-lab/Signal)"
DEFAULT_TIMEOUT = httpx.Timeout(20.0, connect=10.0)


class UnsafeURLError(ValueError):
    pass


def ensure_public_url(url: str) -> None:
    """Reject URLs that resolve to private, loopback, or link-local addresses."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError(f"unsupported scheme: {parsed.scheme!r}")
    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL has no host")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"cannot resolve host {host!r}") from exc
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if not addr.is_global:
            raise UnsafeURLError(f"host {host!r} resolves to non-public address {addr}")


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
    )
