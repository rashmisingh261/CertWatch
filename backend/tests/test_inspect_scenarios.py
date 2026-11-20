"""Inspector scenarios end-to-end through the API, with mocked DNS/TLS (no internet)."""
import socket
import ssl

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import limiter
from app.main import app
from app.services import inspector
from tests.fakenet import FakeNet, cert, handshake

client = TestClient(app)
D = "example.com"


@pytest.fixture(autouse=True)
def net(monkeypatch):
    limiter.reset()
    return FakeNet(monkeypatch)


def inspect(domain=D):
    return client.post("/api/inspect", json={"domain": domain})


def test_valid_certificate(net):
    net.serve(D, cert(D, days=90, issuer="Test CA"))
    j = inspect().json()
    assert j["status"] == "valid" and j["validation"]["trusted"] and j["validation"]["hostname_match"]
    assert j["issuer"]["common_name"] == "Test CA" and j["tls_version"] == "TLSv1.3"
    assert j["validity"]["days_remaining"] in (89, 90) and j["sans"] == [D]
    assert len(j["fingerprint_sha256"].split(":")) == 32 and j["public_key_fingerprint"]


def test_expired_certificate(net):
    net.serve(D, cert(D, days=-2, started_days_ago=60), verify_error="certificate has expired")
    j = inspect().json()
    assert j["status"] == "expired" and j["validity"]["expired"] and j["validity"]["days_remaining"] < 0
    assert j["validation"]["trusted"] is False  # reported, not hidden


def test_hostname_mismatch_is_distinct_from_trust(net):
    net.serve(D, cert(D, sans=["other.example.org"], cn="other.example.org"))
    j = inspect().json()
    assert j["status"] == "hostname_mismatch"
    assert j["validation"]["trusted"] is True and j["validation"]["hostname_match"] is False


def test_invalid_chain_is_untrusted_but_still_displayed(net):
    net.serve(D, cert(D), verify_error="unable to get local issuer certificate")
    j = inspect().json()
    assert j["status"] == "untrusted" and j["validation"]["trusted"] is False
    assert "issuer" in j["validation"]["trust_error"]
    assert j["subject"]["common_name"] == D  # inspection still succeeded


def test_dns_failure(net):
    net.dns_fail.add("nope.example.com")
    r = inspect("nope.example.com")
    assert r.status_code == 502 and r.json()["error"]["code"] == "dns_error"
    assert net.fetch_calls == 0


def test_connection_timeout(net):
    net.fail(D, socket.timeout())
    r = inspect()
    assert r.status_code == 504 and r.json()["error"]["code"] == "timeout"


def test_connection_refused(net):
    net.fail(D, ConnectionRefusedError())
    r = inspect()
    assert r.status_code == 502 and r.json()["error"]["code"] == "connection_failed"


def test_tls_handshake_failure(net):
    net.fail(D, ssl.SSLError("tlsv1 alert protocol version"))
    r = inspect()
    assert r.status_code == 502 and r.json()["error"]["code"] == "tls_error"


def test_unparseable_certificate_is_a_clean_error_not_a_500(net):
    bad = handshake(cert(D))
    bad.der = b"\x30\x03garbage"
    net.sites[D] = bad
    r = inspect()
    assert r.status_code == 502 and r.json()["error"]["code"] == "tls_error"
    assert "could not be parsed" in r.json()["error"]["message"]


def test_falls_back_to_next_address_when_first_fails(net, monkeypatch):
    calls = []

    def fetch(addr, host):
        calls.append(addr.ip)
        if len(calls) == 1:
            raise ConnectionRefusedError()
        return handshake(cert(D))

    monkeypatch.setattr(net, "_getaddrinfo", lambda h: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.35", 443)),
    ])
    from app.core import network_guard
    monkeypatch.setattr(network_guard, "_getaddrinfo", net._getaddrinfo)
    monkeypatch.setattr(inspector, "_fetch", fetch)
    assert inspect().status_code == 200 and calls == ["93.184.216.34", "93.184.216.35"]


@pytest.mark.parametrize("ip", ["10.0.0.1", "127.0.0.1", "169.254.169.254", "192.168.1.1", "::1", "fd00::1"])
def test_non_public_resolution_never_connects(net, ip):
    net.ips["internal.example.com"] = ip
    r = inspect("internal.example.com")
    assert r.status_code == 403 and r.json()["error"]["code"] == "blocked_address"
    assert net.fetch_calls == 0
