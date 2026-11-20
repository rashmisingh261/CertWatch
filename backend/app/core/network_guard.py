"""SSRF protection: only public, globally-routable addresses may be contacted.

DNS rebinding mitigation: we resolve exactly once, validate every returned address,
and the caller connects to the validated IP literal (never the hostname again).
"""
from __future__ import annotations

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import List, Union

from app.core import config
from app.core.errors import BlockedAddressError, DnsResolutionError

IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]

# Ranges that ``is_global`` may not (consistently) flag across Python versions.
_EXTRA_BLOCKED = [
    ipaddress.ip_network(n)
    for n in (
        "0.0.0.0/8",
        "100.64.0.0/10",  # carrier-grade NAT
        "192.0.0.0/24",
        "192.88.99.0/24",
        "198.18.0.0/15",  # benchmarking
        "240.0.0.0/4",  # reserved
        "64:ff9b::/96",  # NAT64 (can embed private v4)
        "64:ff9b:1::/48",
        "2002::/16",  # 6to4
        "2001::/32",  # Teredo
        "100::/64",  # discard-only
        "fc00::/7",
        "fe80::/10",
        "fec0::/10",  # deprecated site-local
    )
]


def is_public_ip(ip: IPAddress) -> bool:
    """True only for a publicly routable unicast address."""
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return is_public_ip(ip.ipv4_mapped)
        if ip.sixtofour is not None or ip.teredo is not None:
            return False
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or not ip.is_global
    ):
        return False
    return not any(ip in net for net in _EXTRA_BLOCKED if net.version == ip.version)


@dataclass(frozen=True)
class ResolvedAddress:
    ip: str
    family: int  # socket.AF_INET / AF_INET6


_dns_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="certwatch-dns")


def _getaddrinfo(host: str):
    return socket.getaddrinfo(host, config.TLS_PORT, type=socket.SOCK_STREAM)


def resolve_public_addresses(host: str) -> List[ResolvedAddress]:
    """Resolve ``host`` once and return its addresses, rejecting if ANY is non-public.

    Rejecting on any bad address (not just filtering) defeats split-horizon / mixed
    answer tricks where an attacker mixes a public and an internal record.
    """
    future = _dns_pool.submit(_getaddrinfo, host)
    try:
        infos = future.result(timeout=config.DNS_TIMEOUT_SECONDS)
    except FutureTimeout:
        future.cancel()
        raise DnsResolutionError("DNS lookup timed out.") from None
    except socket.gaierror:
        raise DnsResolutionError(f"Could not resolve '{host}'. Check the domain name.") from None
    except OSError:
        raise DnsResolutionError("DNS lookup failed.") from None

    results: List[ResolvedAddress] = []
    seen = set()
    for family, _type, _proto, _canon, sockaddr in infos:
        if family not in (socket.AF_INET, socket.AF_INET6):
            continue
        ip_str = sockaddr[0].split("%", 1)[0]  # strip IPv6 scope id
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if not is_public_ip(ip):
            raise BlockedAddressError(
                "The domain resolves to a non-public address; connection refused."
            )
        if ip_str not in seen:
            seen.add(ip_str)
            results.append(ResolvedAddress(ip=ip_str, family=family))
    if not results:
        raise DnsResolutionError(f"No usable addresses found for '{host}'.")
    return results
