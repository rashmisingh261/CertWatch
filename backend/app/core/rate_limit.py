"""Tiny in-memory sliding-window rate limiter (per client key, single process)."""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Dict

from app.core import config
from app.core.errors import RateLimitedError


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window = window_seconds
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                raise RateLimitedError("Too many requests. Please wait a minute and try again.")
            q.append(now)
            if len(self._hits) > 10_000:  # bound memory
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]:
                    del self._hits[k]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter(config.RATE_LIMIT_REQUESTS, config.RATE_LIMIT_WINDOW_SECONDS)

# Separate budget for monitor actions that cause outbound connections.
monitor_limiter = RateLimiter(config.MONITOR_RATE_LIMIT_REQUESTS, config.MONITOR_RATE_LIMIT_WINDOW_SECONDS)
