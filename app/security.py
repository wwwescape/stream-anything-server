"""Who may talk to the server: home-network clients that know the access key."""

from __future__ import annotations

import hmac
import ipaddress

from fastapi import Request

# Private (RFC 1918), loopback, link-local, and IPv6 unique-local ranges — i.e. devices on the
# same home network. Anything else (the internet, a misconfigured router port-forward) is refused.
_HOME_NETWORKS = tuple(
    ipaddress.ip_network(n)
    for n in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
)


def is_home_network(host: str | None) -> bool:
    if not host:
        return False
    try:
        address = ipaddress.ip_address(host.split("%")[0])  # drop an IPv6 zone id
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return any(address in network for network in _HOME_NETWORKS)


def presented_key(request: Request) -> str | None:
    """The key from the `key` query parameter (what pasted links carry) or the X-Access-Key header."""
    return request.query_params.get("key") or request.headers.get("x-access-key")


def key_matches(presented: str | None, expected: str) -> bool:
    return presented is not None and hmac.compare_digest(presented.encode(), expected.encode())
