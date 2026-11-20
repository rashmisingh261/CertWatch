"""Mock DNS + TLS underneath the real inspection code (no internet needed)."""
from __future__ import annotations

import datetime as dt
import socket
from typing import Dict, Optional

from cryptography import x509
from cryptography.hazmat.primitives import serialization

from app.core import network_guard
from app.services import inspector
from tests.certgen import make_pem

PUBLIC_IP = "93.184.216.34"


def cert(domain: str, days: float = 90, issuer: str = "Test CA", sans=None, key=None,
         serial: int = 1000, started_days_ago: float = 1, cn: Optional[str] = None) -> bytes:
    now = dt.datetime.now(dt.timezone.utc)
    return make_pem(
        cn=cn or domain, issuer_cn=issuer, sans=[domain] if sans is None else sans, key=key,
        serial=serial, not_before=now - dt.timedelta(days=started_days_ago),
        not_after=now + dt.timedelta(days=days),
    )


def handshake(pem: bytes, tls: str = "TLSv1.3", verify_error: Optional[str] = None):
    der = x509.load_pem_x509_certificate(pem).public_bytes(serialization.Encoding.DER)
    return inspector._Handshake(der, tls, "TLS_AES_256_GCM_SHA384", verify_error,
                                18 if verify_error else None)


class FakeNet:
    def __init__(self, monkeypatch):
        self.sites: Dict[str, object] = {}
        self.ips: Dict[str, str] = {}
        self.dns_fail = set()
        self.fetch_calls = 0
        monkeypatch.setattr(network_guard, "_getaddrinfo", self._getaddrinfo)
        monkeypatch.setattr(inspector, "_fetch", self._fetch)

    def _getaddrinfo(self, host):
        if host in self.dns_fail:
            raise socket.gaierror(8, "no such host")
        ip = self.ips.get(host, PUBLIC_IP)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]

    def _fetch(self, addr, host):
        self.fetch_calls += 1
        site = self.sites[host]
        if isinstance(site, BaseException):
            raise site
        return site

    def serve(self, host, pem, **kw):
        self.sites[host] = handshake(pem, **kw)

    def fail(self, host, exc=None):
        self.sites[host] = exc or ConnectionRefusedError()
