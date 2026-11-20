import threading
import time

import pytest

from app.core import config
from app.core.errors import BusyError, InspectionTimeoutError, RateLimitedError
from app.core.rate_limit import RateLimiter
from app.services import runner


def test_busy_when_all_slots_taken(monkeypatch):
    sem = threading.BoundedSemaphore(1)
    sem.acquire()
    monkeypatch.setattr(runner, "_slots", sem)
    with pytest.raises(BusyError):
        runner.run_inspection("example.com")


def test_deadline_cancels_slow_inspection_and_releases_slot_afterwards(monkeypatch):
    monkeypatch.setattr(config, "OVERALL_DEADLINE_SECONDS", 0.1)
    monkeypatch.setattr(runner, "inspect_domain", lambda d: time.sleep(0.4))
    sem = threading.BoundedSemaphore(2)
    monkeypatch.setattr(runner, "_slots", sem)
    with pytest.raises(InspectionTimeoutError):
        runner.run_inspection("example.com")
    time.sleep(0.6)  # the worker finishes; its slot must come back (cap not leaked)
    assert sem.acquire(blocking=False) and sem.acquire(blocking=False)


def test_slot_released_after_normal_run(monkeypatch):
    monkeypatch.setattr(runner, "inspect_domain", lambda d: "ok")
    sem = threading.BoundedSemaphore(1)
    monkeypatch.setattr(runner, "_slots", sem)
    assert runner.run_inspection("x.example.com") == "ok"
    assert sem.acquire(blocking=False)


def test_rate_limiter_window(monkeypatch):
    lim = RateLimiter(2, 0.2)
    lim.check("a")
    lim.check("a")
    with pytest.raises(RateLimitedError):
        lim.check("a")
    lim.check("b")  # separate client unaffected
    time.sleep(0.25)
    lim.check("a")  # window expired
