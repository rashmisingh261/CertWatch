import datetime as dt
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.db import init_db
from app.main import app
from app.services import monitor
from tests.certgen import new_ec_key
from tests.fakenet import FakeNet, cert

pytestmark = pytest.mark.usefixtures("monitor_env")
client = TestClient(app)
D = "example.com"


@pytest.fixture
def net(monkeypatch):
    return FakeNet(monkeypatch)


def add(domain=D):
    return client.post("/api/monitor", json={"domain": domain})


def check(i):
    return client.post(f"/api/monitor/{i}/check")


def count(table, monitor_env):
    c = sqlite3.connect(str(monitor_env))
    try:
        return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        c.close()


# --------------------------------------------------------------------------- adding
def test_add_domain_stores_certificate_info(net):
    net.serve(D, cert(D, days=90, issuer="Test CA"), tls="TLSv1.3")
    r = add()
    assert r.status_code == 201
    j = r.json()
    assert j["domain"] == D and j["status"] == "HEALTHY"
    assert j["issuer"] == "Test CA" and j["tls_version"] == "TLSv1.3"
    assert j["days_remaining"] in (89, 90)
    assert len(j["fingerprint_sha256"].split(":")) == 32
    assert j["last_checked_at"] and j["added_at"] and j["last_error"] is None
    assert len(j["observations"]) == 1 and j["observations"][0]["changed"] is False
    assert j["observations"][0]["sans"] == [D]


def test_add_normalises_domain(net):
    net.serve(D, cert(D))
    assert add("  Example.COM. ").json()["domain"] == D


def test_duplicate_domain_rejected_without_network_call(net):
    net.serve(D, cert(D))
    assert add().status_code == 201
    calls = net.fetch_calls
    for variant in (D, "EXAMPLE.com", "example.com."):
        r = add(variant)
        assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_domain"
    assert net.fetch_calls == calls  # rejected before connecting
    assert len(client.get("/api/monitor").json()) == 1


@pytest.mark.parametrize("bad", ["localhost", "http://example.com", "example.com:8443", "127.0.0.1", ""])
def test_invalid_domains_not_saved(bad, net):
    r = add(bad)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_domain"
    assert client.get("/api/monitor").json() == []
    assert net.fetch_calls == 0


def test_private_resolution_blocked_and_not_saved(net):
    net.ips["intranet.example.com"] = "10.0.0.5"
    r = add("intranet.example.com")
    assert r.status_code == 403 and r.json()["error"]["code"] == "blocked_address"
    assert net.fetch_calls == 0 and client.get("/api/monitor").json() == []


def test_dns_failure_on_add_not_saved(net):
    net.dns_fail.add("typo.example.com")
    r = add("typo.example.com")
    assert r.status_code == 502 and r.json()["error"]["code"] == "dns_error"
    assert client.get("/api/monitor").json() == []


def test_connection_failure_on_add_is_saved_as_check_failed(net):
    net.fail(D)
    r = add()
    assert r.status_code == 201
    j = r.json()
    assert j["status"] == "CHECK_FAILED" and "connect" in j["last_error"].lower()
    assert j["fingerprint_sha256"] is None and j["days_remaining"] is None
    obs = j["observations"][0]
    assert obs["outcome"] == "failed" and obs["error_code"] == "connection_failed"


def test_domain_limit(net, monkeypatch):
    monkeypatch.setattr(config, "MONITOR_MAX_DOMAINS", 1)
    net.serve(D, cert(D))
    net.serve("b.example.com", cert("b.example.com"))
    assert add().status_code == 201
    r = add("b.example.com")
    assert r.status_code == 409 and r.json()["error"]["code"] == "limit_reached"


# ------------------------------------------------------------------ list/get/delete
def test_list_domains(net):
    for d in ("zeta.example.com", "alpha.example.com"):
        net.serve(d, cert(d))
        add(d)
    rows = client.get("/api/monitor").json()
    assert [r["domain"] for r in rows] == ["alpha.example.com", "zeta.example.com"]
    assert all("observations" not in r and r["status"] == "HEALTHY" for r in rows)


def test_get_detail_and_unknown_id(net):
    net.serve(D, cert(D))
    i = add().json()["id"]
    assert client.get(f"/api/monitor/{i}").json()["domain"] == D
    r = client.get("/api/monitor/9999")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    r = client.get("/api/monitor/abc")
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


def test_delete_domain_removes_history(net, monitor_env):
    net.serve(D, cert(D))
    i = add().json()["id"]
    check(i)
    assert count("observations", monitor_env) == 2
    assert client.delete(f"/api/monitor/{i}").status_code == 204
    assert client.get(f"/api/monitor/{i}").status_code == 404
    assert client.get("/api/monitor").json() == []
    assert count("observations", monitor_env) == 0  # cascade
    assert client.delete(f"/api/monitor/{i}").status_code == 404


# -------------------------------------------------------------------------- checks
def test_successful_check_unchanged(net):
    net.serve(D, cert(D, serial=5))
    first = add().json()
    j = check(first["id"]).json()
    assert j["status"] == "HEALTHY" and len(j["observations"]) == 2
    assert j["observations"][0]["changed"] is False and j["observations"][0]["changes"] is None
    assert j["fingerprint_sha256"] == first["fingerprint_sha256"]
    assert j["last_checked_at"] >= first["last_checked_at"] and j["last_changed_at"] is None


def test_expired_certificate(net):
    net.serve(D, cert(D, days=-3, started_days_ago=100))
    j = add().json()
    assert j["status"] == "EXPIRED" and j["days_remaining"] < 0
    assert j["observations"][0]["status"] == "EXPIRED"


@pytest.mark.parametrize("days,expected", [(10, "EXPIRING_SOON"), (29.5, "EXPIRING_SOON"),
                                           (29.99, "EXPIRING_SOON"), (31, "HEALTHY"), (90, "HEALTHY")])
def test_expiry_thresholds(net, days, expected):
    net.serve(D, cert(D, days=days))
    assert add().json()["status"] == expected


def test_untrusted_chain_is_invalid(net):
    net.serve(D, cert(D), verify_error="self-signed certificate")
    j = add().json()
    assert j["status"] == "INVALID"
    assert j["observations"][0]["trusted"] is False
    assert j["observations"][0]["trust_error"] == "self-signed certificate"


def test_hostname_mismatch_is_invalid(net):
    net.serve(D, cert(D, sans=["other.example.org"], cn="other.example.org"))
    j = add().json()
    assert j["status"] == "INVALID" and j["observations"][0]["hostname_match"] is False


def test_expired_takes_precedence_over_invalid(net):
    net.serve(D, cert(D, days=-1, started_days_ago=50), verify_error="certificate has expired")
    assert add().json()["status"] == "EXPIRED"


def test_failed_check_keeps_last_known_certificate(net):
    net.serve(D, cert(D, days=90, issuer="Test CA"))
    first = add().json()
    net.fail(D)
    j = check(first["id"]).json()
    assert j["status"] == "CHECK_FAILED" and j["last_error"]
    assert j["fingerprint_sha256"] == first["fingerprint_sha256"]  # not wiped
    assert j["issuer"] == "Test CA" and j["days_remaining"] in (89, 90)
    assert [o["outcome"] for o in j["observations"]] == ["failed", "ok"]


def test_unparseable_server_certificate_is_recorded_as_failed_check(net):
    from tests.fakenet import handshake
    net.serve(D, cert(D))
    i = add().json()["id"]
    bad = handshake(cert(D))
    bad.der = b"\x30\x03garbage"
    net.sites[D] = bad
    r = check(i)
    assert r.status_code == 200  # recorded, not a 500
    j = r.json()
    assert j["status"] == "CHECK_FAILED" and j["observations"][0]["error_code"] == "tls_error"


def test_timeout_and_tls_errors_become_check_failed(net):
    import socket
    net.serve(D, cert(D))
    i = add().json()["id"]
    net.fail(D, socket.timeout())
    j = check(i).json()
    assert j["status"] == "CHECK_FAILED" and j["observations"][0]["error_code"] == "timeout"


def test_recovery_after_failure_is_not_a_change(net):
    pem = cert(D, serial=7)
    net.serve(D, pem)
    i = add().json()["id"]
    net.fail(D)
    assert check(i).json()["status"] == "CHECK_FAILED"
    net.serve(D, pem)  # same certificate comes back
    j = check(i).json()
    # Compared against the last *successful* observation, so the failure in between is ignored.
    assert j["status"] == "HEALTHY" and j["observations"][0]["changed"] is False
    assert [o["outcome"] for o in j["observations"]] == ["ok", "failed", "ok"]


# ----------------------------------------------------------------- change detection
def test_fingerprint_change_detected_with_details(net):
    old = cert(D, issuer="CA One", sans=[D, "www.example.com"], serial=1, key=new_ec_key())
    new = cert(D, issuer="CA Two", sans=[D, "api.example.com"], serial=2, key=new_ec_key(), days=120)
    net.serve(D, old)
    first = add().json()
    net.serve(D, new)
    j = check(first["id"]).json()

    assert j["status"] == "CHANGED" and j["last_changed_at"]
    assert j["fingerprint_sha256"] != first["fingerprint_sha256"]
    latest = j["observations"][0]
    assert latest["changed"] is True
    ch = latest["changes"]
    keys = {f["key"]: f for f in ch["fields"]}
    assert keys["issuer"]["before"] == "CN=CA One" and keys["issuer"]["after"] == "CN=CA Two"
    assert {"serial_number", "not_after", "public_key_fingerprint"} <= set(keys)
    assert "subject" not in keys  # unchanged fields are not listed
    assert ch["sans_added"] == ["api.example.com"]
    assert ch["sans_removed"] == ["www.example.com"]
    assert "different CA" in ch["hint"]
    assert "malicious" not in ch["hint"].lower() and "attack" not in ch["hint"].lower()


def test_history_preserves_previous_observation(net, monitor_env):
    old, new = cert(D, serial=1, key=new_ec_key()), cert(D, serial=2, key=new_ec_key())
    net.serve(D, old)
    first = add().json()
    net.serve(D, new)
    j = check(first["id"]).json()
    obs = j["observations"]
    assert len(obs) == 2 and count("observations", monitor_env) == 2
    assert obs[1]["fingerprint_sha256"] == first["fingerprint_sha256"]  # original kept intact
    assert obs[1]["changed"] is False and obs[1]["serial_number"] == "1"
    assert obs[0]["fingerprint_sha256"] == j["fingerprint_sha256"] != obs[1]["fingerprint_sha256"]
    assert obs[0]["serial_number"] == "2"


def test_same_key_same_issuer_looks_like_routine_renewal(net):
    key = new_ec_key()
    net.serve(D, cert(D, key=key, serial=1, days=20))
    i = add().json()["id"]
    net.serve(D, cert(D, key=key, serial=2, days=90))
    ch = check(i).json()["observations"][0]["changes"]
    keys = {f["key"] for f in ch["fields"]}
    assert "issuer" not in keys and "public_key_fingerprint" not in keys
    assert {"serial_number", "not_after"} <= keys
    assert "routine renewal" in ch["hint"]


def test_new_key_same_issuer_hint(net):
    net.serve(D, cert(D, serial=1, key=new_ec_key()))
    i = add().json()["id"]
    net.serve(D, cert(D, serial=2, key=new_ec_key()))
    ch = check(i).json()["observations"][0]["changes"]
    assert "issuer" not in {f["key"] for f in ch["fields"]}
    assert "new public key" in ch["hint"]


def test_change_to_expired_cert_reports_expired_but_records_change(net):
    net.serve(D, cert(D, serial=1, key=new_ec_key()))
    i = add().json()["id"]
    net.serve(D, cert(D, serial=2, key=new_ec_key(), days=-1, started_days_ago=40))
    j = check(i).json()
    assert j["status"] == "EXPIRED" and j["observations"][0]["changed"] is True


def test_changed_status_clears_on_next_unchanged_check_but_history_remains(net):
    net.serve(D, cert(D, serial=1, key=new_ec_key()))
    i = add().json()["id"]
    new = cert(D, serial=2, key=new_ec_key())
    net.serve(D, new)
    assert check(i).json()["status"] == "CHANGED"
    j = check(i).json()
    assert j["status"] == "HEALTHY"
    assert [o["changed"] for o in j["observations"]] == [False, True, False]
    assert j["last_changed_at"] is not None  # still visible on the domain


def test_check_on_unknown_domain(net):
    r = check(12345)
    assert r.status_code == 404


def test_check_revalidates_ssrf_every_time(net):
    net.serve(D, cert(D))
    i = add().json()["id"]
    calls = net.fetch_calls
    net.ips[D] = "169.254.169.254"  # DNS now points at cloud metadata
    j = check(i).json()
    assert j["status"] == "CHECK_FAILED" and j["observations"][0]["error_code"] == "blocked_address"
    assert net.fetch_calls == calls  # never connected


# ------------------------------------------------------------------- abuse controls
def test_per_domain_cooldown(net, monkeypatch):
    monkeypatch.setattr(config, "MONITOR_CHECK_COOLDOWN_SECONDS", 60)
    net.serve(D, cert(D))
    i = add().json()["id"]
    r = check(i)
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"
    assert "wait" in r.json()["error"]["message"].lower()


def test_rate_limit_on_add_and_check(net):
    for _ in range(config.MONITOR_RATE_LIMIT_REQUESTS):
        add("localhost")  # rejected by validation but still consumes budget
    assert add("localhost").status_code == 429
    assert check(1).status_code == 429


def test_inspector_rate_limit_is_independent(net):
    net.serve(D, cert(D))
    for _ in range(config.MONITOR_RATE_LIMIT_REQUESTS):
        add("localhost")
    assert client.post("/api/inspect", json={"domain": "localhost"}).status_code == 422  # not 429


# --------------------------------------------------------------------- persistence
def test_data_persists_across_restart(net, monitor_env):
    net.serve(D, cert(D, issuer="Persist CA"))
    i = add().json()["id"]
    init_db()  # a restart re-runs schema creation: must not wipe data
    with TestClient(app) as fresh:  # runs the app lifespan (init_db) like a real startup
        rows = fresh.get("/api/monitor").json()
        assert [r["domain"] for r in rows] == [D]
        assert rows[0]["issuer"] == "Persist CA"
        assert len(fresh.get(f"/api/monitor/{i}").json()["observations"]) == 1


def test_no_certificate_content_stored(net, monitor_env):
    net.serve(D, cert(D))
    add()
    c = sqlite3.connect(str(monitor_env))
    try:
        cols = [r[1] for r in c.execute("PRAGMA table_info(observations)")]
        text = " ".join(str(v) for row in c.execute("SELECT * FROM observations") for v in row)
    finally:
        c.close()
    assert not any(k in " ".join(cols).lower() for k in ("pem", "der", "private", "raw"))
    assert "BEGIN" not in text


# ------------------------------------------------------------------ pure status logic
def _aged(stored, days, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    return monitor.effective_status(stored, (now + dt.timedelta(days=days)).isoformat(), now)


def test_status_ages_with_time():
    assert _aged("HEALTHY", 90) == "HEALTHY"
    assert _aged("HEALTHY", 10) == "EXPIRING_SOON"   # was healthy at check time
    assert _aged("HEALTHY", -1) == "EXPIRED"
    assert _aged("EXPIRING_SOON", -1) == "EXPIRED"
    assert _aged("CHANGED", 5) == "CHANGED"
    assert _aged("CHANGED", -1) == "EXPIRED"
    assert _aged("INVALID", 5) == "INVALID"
    assert _aged("CHECK_FAILED", -1) == "CHECK_FAILED"  # never aged
    assert monitor.effective_status("CHECK_FAILED", None, dt.datetime.now(dt.timezone.utc)) == "CHECK_FAILED"


def test_list_shows_aged_status(net, monitor_env):
    net.serve(D, cert(D, days=90))
    i = add().json()["id"]
    soon = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=5)).isoformat()
    c = sqlite3.connect(str(monitor_env))
    c.execute("UPDATE monitored_domains SET not_after = ? WHERE id = ?", (soon, i))
    c.commit()
    c.close()
    row = client.get("/api/monitor").json()[0]
    assert row["status"] == "EXPIRING_SOON" and row["days_remaining"] == 4


def test_phase1_and_phase2_still_work(net):
    net.serve(D, cert(D))
    r = client.post("/api/inspect", json={"domain": D})
    assert r.status_code == 200 and r.json()["public_key_fingerprint"]
    assert client.get("/api/health").json() == {"status": "ok"}
