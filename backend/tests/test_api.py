import pytest
from fastapi.testclient import TestClient

from app.core import network_guard
from app.core.rate_limit import limiter
from app.main import app
from app.services import inspector
from tests.helpers import make_cert

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset():
    limiter.reset()


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


@pytest.mark.parametrize("d", ["localhost", "http://example.com", "example.com:8080", "127.0.0.1"])
def test_bad_domains_rejected(d):
    r = client.post("/api/inspect", json={"domain": d})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_domain"


def test_bad_body():
    r = client.post("/api/inspect", json={"nope": 1})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


def test_private_resolution_blocked(monkeypatch):
    monkeypatch.setattr(
        network_guard, "_getaddrinfo",
        lambda h: [(2, 1, 6, "", ("192.168.0.10", 443))],
    )
    r = client.post("/api/inspect", json={"domain": "intranet.example.com"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "blocked_address"


def test_dns_error(monkeypatch):
    import socket
    def boom(h): raise socket.gaierror()
    monkeypatch.setattr(network_guard, "_getaddrinfo", boom)
    r = client.post("/api/inspect", json={"domain": "nonexistent.example.com"})
    assert r.status_code == 502 and r.json()["error"]["code"] == "dns_error"


def test_success_shape(monkeypatch):
    _, _, der = make_cert(["example.com"], cn="example.com")
    hs = inspector._Handshake(der, "TLSv1.3", "X", None, None)
    monkeypatch.setattr(network_guard, "_getaddrinfo", lambda h: [(2, 1, 6, "", ("93.184.216.34", 443))])
    monkeypatch.setattr(inspector, "_fetch", lambda a, h: hs)
    r = client.post("/api/inspect", json={"domain": "Example.com"})
    assert r.status_code == 200
    j = r.json()
    assert j["domain"] == "example.com" and j["status"] == "valid"
    assert j["validation"]["trusted"] is True and j["tls_version"] == "TLSv1.3"


def test_rate_limit(monkeypatch):
    for _ in range(10):
        client.post("/api/inspect", json={"domain": "localhost"})
    r = client.post("/api/inspect", json={"domain": "localhost"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"
