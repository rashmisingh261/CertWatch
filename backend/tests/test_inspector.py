import datetime as dt
import socket

import pytest

from app.core import config
from app.core.network_guard import ResolvedAddress
from app.services import inspector
from tests.helpers import TlsServer, make_cert

LOCAL = ResolvedAddress("127.0.0.1", socket.AF_INET)


def _report(host, names, **kw):
    _, _, der = make_cert(names, **kw)
    hs = inspector._Handshake(der, "TLSv1.3", "TLS_AES_256_GCM_SHA384", None, None)
    return inspector.build_report(host, "93.184.216.34", hs)


def test_report_fields():
    r = _report("test.example", ["test.example", "www.test.example"])
    assert r.sans == ["test.example", "www.test.example"]
    assert r.subject.common_name == "test.example"
    assert r.subject.organization == "CertWatch Test"
    assert len(r.fingerprint_sha256.split(":")) == 32
    assert r.validity.days_remaining in (89, 90)
    assert r.status == "valid" and r.validation.trusted and r.validation.hostname_match
    assert r.tls_version == "TLSv1.3"


def test_expiring_soon():
    now = dt.datetime.now(dt.timezone.utc)
    r = _report("test.example", ["test.example"], not_after=now + dt.timedelta(days=5, hours=1))
    assert r.validity.days_remaining == 5 and r.status == "expiring_soon"


def test_expired():
    now = dt.datetime.now(dt.timezone.utc)
    r = _report(
        "test.example", ["test.example"],
        not_before=now - dt.timedelta(days=100), not_after=now - dt.timedelta(days=2),
    )
    assert r.validity.expired and r.validity.days_remaining < 0 and r.status == "expired"


def test_hostname_mismatch_reported_separately():
    r = _report("other.example", ["test.example"])
    assert r.validation.trusted and not r.validation.hostname_match
    assert r.status == "hostname_mismatch"


def test_untrusted_flag():
    _, _, der = make_cert(["test.example"])
    hs = inspector._Handshake(der, "TLSv1.3", None, "self-signed certificate", 18)
    r = inspector.build_report("test.example", "1.2.3.4", hs)
    assert not r.validation.trusted and r.validation.trust_error_code == 18
    assert r.status == "untrusted"


@pytest.fixture
def server(tmp_path, monkeypatch):
    cert, key, _ = make_cert(["test.example"])
    srv = TlsServer(cert, key, tmp_path)
    monkeypatch.setattr(config, "TLS_PORT", srv.port)
    yield srv, cert
    srv.close()


def test_live_self_signed_is_untrusted_but_inspectable(server):
    hs = inspector._fetch(LOCAL, "test.example")
    assert hs.verify_error is not None  # NOT trusted: not in CA bundle
    assert hs.der and hs.tls_version.startswith("TLSv1")


def test_live_trusted_when_in_ca_bundle(server, tmp_path, monkeypatch):
    srv, cert = server
    ca = tmp_path / "ca.pem"
    ca.write_bytes(cert)
    monkeypatch.setattr(inspector.certifi, "where", lambda: str(ca))
    hs = inspector._fetch(LOCAL, "test.example")
    assert hs.verify_error is None


def test_connection_refused(monkeypatch):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    monkeypatch.setattr(config, "TLS_PORT", port)
    monkeypatch.setattr(inspector, "validate_domain", lambda d: d)
    monkeypatch.setattr(inspector, "resolve_public_addresses", lambda h: [LOCAL])
    from app.core.errors import ConnectionFailedError
    with pytest.raises(ConnectionFailedError):
        inspector.inspect_domain("test.example")


def test_non_tls_server(monkeypatch):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    monkeypatch.setattr(config, "TLS_PORT", srv.getsockname()[1])
    monkeypatch.setattr(inspector, "validate_domain", lambda d: d)
    monkeypatch.setattr(inspector, "resolve_public_addresses", lambda h: [LOCAL])
    monkeypatch.setattr(config, "HANDSHAKE_TIMEOUT_SECONDS", 0.5)
    from app.core.errors import CertWatchError
    with pytest.raises(CertWatchError):
        inspector.inspect_domain("test.example")
    srv.close()
