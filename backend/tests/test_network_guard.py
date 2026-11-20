import ipaddress
import socket

import pytest

from app.core import network_guard
from app.core.errors import BlockedAddressError, DnsResolutionError


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1", "10.1.2.3", "172.16.0.1", "192.168.1.1", "169.254.169.254",
        "0.0.0.0", "224.0.0.1", "240.0.0.1", "100.64.0.1", "198.18.0.1",
        "::1", "::", "fe80::1", "fc00::1", "fd00:ec2::254", "ff02::1",
        "::ffff:127.0.0.1", "::ffff:10.0.0.1", "64:ff9b::7f00:1", "2002:7f00:1::1",
        "2001:db8::1",
    ],
)
def test_blocked(ip):
    assert not network_guard.is_public_ip(ipaddress.ip_address(ip))


@pytest.mark.parametrize("ip", ["93.184.216.34", "8.8.8.8", "1.1.1.1", "2606:4700:4700::1111"])
def test_public(ip):
    assert network_guard.is_public_ip(ipaddress.ip_address(ip))


def _fake(addrs):
    def fake(host):
        return [
            (socket.AF_INET6 if ":" in a else socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 443))
            for a in addrs
        ]
    return fake


def test_resolves_public(monkeypatch):
    monkeypatch.setattr(network_guard, "_getaddrinfo", _fake(["93.184.216.34"]))
    out = network_guard.resolve_public_addresses("example.com")
    assert [a.ip for a in out] == ["93.184.216.34"]


def test_rejects_private(monkeypatch):
    monkeypatch.setattr(network_guard, "_getaddrinfo", _fake(["10.0.0.5"]))
    with pytest.raises(BlockedAddressError):
        network_guard.resolve_public_addresses("internal.example.com")


def test_rejects_mixed_answers(monkeypatch):
    """One public + one internal record must be refused outright (rebinding trick)."""
    monkeypatch.setattr(network_guard, "_getaddrinfo", _fake(["93.184.216.34", "127.0.0.1"]))
    with pytest.raises(BlockedAddressError):
        network_guard.resolve_public_addresses("evil.example.com")


def test_dns_failure(monkeypatch):
    def boom(host):
        raise socket.gaierror(8, "nodename nor servname")
    monkeypatch.setattr(network_guard, "_getaddrinfo", boom)
    with pytest.raises(DnsResolutionError):
        network_guard.resolve_public_addresses("nope.example.com")
