"""Announces the server on the home network (mDNS / DNS-SD), so Stream Anything can find it
without anyone typing an IP address. The announcement carries the server's name and port only —
never the access key."""

from __future__ import annotations

import logging
import socket

from app import __version__
from app.security import is_home_network

# Same naming family as the app's own services (_streamanything._tcp for TVs, _streamanyphone._tcp for
# phones); DNS-SD service names are limited to 15 bytes.
SERVICE_TYPE = "_streamanymedia._tcp.local."

log = logging.getLogger(__name__)


def lan_addresses() -> list[str]:
    """This computer's IPv4 addresses on the home network (best effort).

    Only private home-network addresses count: a VPN like Tailscale adds its own interface
    (100.64.0.0/10) — often the one the OS would route through — which phones and TVs without that
    VPN can't reach, and which the server refuses anyway."""
    candidates: set[str] = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # No packet is sent for a UDP connect(); it just asks the OS which address it would use.
            s.connect(("192.0.2.1", 9))
            candidates.add(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            candidates.add(info[4][0])
    except OSError:
        pass
    return sorted(a for a in candidates if is_home_network(a) and not a.startswith(("127.", "169.254.")))


class Announcer:
    """Registers the service while the server runs; `close()` withdraws it."""

    def __init__(self, name: str, port: int):
        self._zeroconf = None
        self._info = None
        try:
            from zeroconf import ServiceInfo, Zeroconf

            addresses = [socket.inet_aton(a) for a in lan_addresses()]
            if not addresses:
                return
            safe_name = name.replace(".", " ")[:60]
            self._info = ServiceInfo(
                SERVICE_TYPE,
                f"{safe_name}.{SERVICE_TYPE}",
                addresses=addresses,
                port=port,
                properties={"name": name, "version": __version__, "api": "/api/v1"},
                server=f"{socket.gethostname()}.local.",
            )
            self._zeroconf = Zeroconf()
            self._zeroconf.register_service(self._info, allow_name_change=True)
        except Exception as exc:  # discovery is a convenience; never let it stop the server
            log.warning("Couldn't announce on the network (mDNS): %s", exc)
            self._zeroconf = None

    def close(self) -> None:
        if self._zeroconf is not None:
            try:
                self._zeroconf.unregister_service(self._info)
            finally:
                self._zeroconf.close()
