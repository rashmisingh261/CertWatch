"""The demo helper used for docs/screenshots must keep working (and stay offline)."""
import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core import config, network_guard
from app.core.rate_limit import limiter, monitor_limiter
from app.db import init_db
from app.main import app
from app.services import inspector

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "demo.py"


@pytest.fixture
def demo(tmp_path, monkeypatch):
    # Register restores for everything build_demo_app() patches globally.
    monkeypatch.setattr(config, "DB_PATH", config.DB_PATH)
    monkeypatch.setattr(config, "MONITOR_CHECK_COOLDOWN_SECONDS", config.MONITOR_CHECK_COOLDOWN_SECONDS)
    monkeypatch.setattr(network_guard, "_getaddrinfo", network_guard._getaddrinfo)
    monkeypatch.setattr(inspector, "_fetch", inspector._fetch)
    spec = importlib.util.spec_from_file_location("certwatch_demo", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.build_demo_app(str(tmp_path / "demo.db"))
    limiter.reset()
    monitor_limiter.reset()
    init_db()
    return module, TestClient(app)


def test_demo_sites_cover_each_screenshot_state(demo):
    _, client = demo
    status = {
        d: client.post("/api/inspect", json={"domain": d})
        for d in ("example.com", "expiring.example.com", "expired.example.com",
                  "mismatch.example.org", "selfsigned.example.net", "down.example.com", "nope.example.com")
    }
    assert status["example.com"].json()["status"] == "valid"
    assert status["expiring.example.com"].json()["status"] == "expiring_soon"
    assert status["expired.example.com"].json()["status"] == "expired"
    assert status["mismatch.example.org"].json()["status"] == "hostname_mismatch"
    assert status["selfsigned.example.net"].json()["status"] == "untrusted"
    assert status["down.example.com"].status_code == 502
    assert status["nope.example.com"].json()["error"]["code"] == "dns_error"


def test_walkthrough_detects_change_after_rotation(demo):
    module, client = demo
    added = client.post("/api/monitor", json={"domain": "example.com"}).json()
    assert added["status"] == "HEALTHY"
    module.rotate("example.com")
    checked = client.post(f"/api/monitor/{added['id']}/check").json()
    assert checked["status"] == "CHANGED"
    changes = checked["observations"][0]["changes"]
    assert changes["sans_removed"] == ["www.example.com"] and changes["sans_added"] == ["api1.example.com"]
    assert len(checked["observations"]) == 2  # history preserved


def test_certs_command_writes_public_certificates_only(demo, tmp_path):
    module, _ = demo
    module.main(["certs", str(tmp_path / "out")])
    files = sorted(p.name for p in (tmp_path / "out").iterdir())
    assert files == ["certificate-a.pem", "certificate-b.pem"]
    for p in (tmp_path / "out").iterdir():
        text = p.read_text()
        assert "BEGIN CERTIFICATE" in text and "PRIVATE KEY" not in text
    with TestClient(app) as c:
        r = c.post("/api/certdiff", files={
            "certificate_a": ("a.pem", (tmp_path / "out" / "certificate-a.pem").read_bytes()),
            "certificate_b": ("b.pem", (tmp_path / "out" / "certificate-b.pem").read_bytes()),
        })
    sans = next(f for f in r.json()["fields"] if f["key"] == "sans")
    assert sans["removed"] == ["DNS:www.example.com"] and sans["added"] == ["DNS:api.example.com"]


def test_rotate_rejects_unknown_or_down_sites(demo):
    module, _ = demo
    for bad in ("nope.example.com", "down.example.com"):
        with pytest.raises(KeyError):
            module.rotate(bad)
