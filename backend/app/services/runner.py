"""Shared, bounded execution of certificate inspections.

Both the Inspector API and the Monitor go through here so there is ONE global cap on
concurrent outbound connections and ONE overall deadline.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from app.core import config
from app.core.errors import BusyError, InspectionTimeoutError
from app.schemas import InspectResponse
from app.services.inspector import inspect_domain

_slots = threading.BoundedSemaphore(config.MAX_CONCURRENT_INSPECTIONS)
_pool = ThreadPoolExecutor(
    max_workers=config.MAX_CONCURRENT_INSPECTIONS, thread_name_prefix="certwatch-inspect"
)


def _run(domain: str) -> InspectResponse:
    try:
        return inspect_domain(domain)
    finally:
        _slots.release()


def run_inspection(domain: str) -> InspectResponse:
    """Validate + inspect ``domain`` (see inspector.inspect_domain) under the global limits."""
    if not _slots.acquire(blocking=False):
        raise BusyError("Server is busy. Please try again shortly.")
    try:
        future = _pool.submit(_run, domain)
    except Exception:
        _slots.release()
        raise
    try:
        return future.result(timeout=config.OVERALL_DEADLINE_SECONDS)
    except FutureTimeout:
        raise InspectionTimeoutError("The inspection took too long and was cancelled.") from None
