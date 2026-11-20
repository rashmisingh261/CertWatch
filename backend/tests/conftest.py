import pytest

from app.core import config
from app.core.rate_limit import limiter, monitor_limiter
from app.db import init_db


@pytest.fixture
def monitor_env(tmp_path, monkeypatch):
    """Isolated SQLite file per test, no cooldown, fresh rate limiters."""
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(config, "MONITOR_CHECK_COOLDOWN_SECONDS", 0)
    limiter.reset()
    monitor_limiter.reset()
    init_db()
    yield tmp_path / "test.db"
    monitor_limiter.reset()
