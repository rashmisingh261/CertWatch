"""Central, hard-coded security configuration.

The target port is deliberately a constant and NOT configurable per request.
"""
from __future__ import annotations

import os
from pathlib import Path

TLS_PORT = 443  # the only port CertWatch will ever connect to

DNS_TIMEOUT_SECONDS = 3.0
CONNECT_TIMEOUT_SECONDS = 5.0  # TCP connect
HANDSHAKE_TIMEOUT_SECONDS = 5.0  # TLS handshake / read
OVERALL_DEADLINE_SECONDS = 15.0  # whole inspection, enforced by the API layer

MAX_ADDRESSES_TRIED = 3  # cap on how many resolved IPs we try
MAX_CONCURRENT_INSPECTIONS = 8

RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60

# CertDiff uploads
MAX_UPLOAD_BYTES = 1_000_000  # per certificate file (1 MB)
MAX_REQUEST_BYTES = 2 * MAX_UPLOAD_BYTES + 64 * 1024  # two files + multipart overhead

# Monitor (SQLite)
DB_PATH = os.environ.get(
    "CERTWATCH_DB_PATH",
    str(Path(__file__).resolve().parents[2] / "data" / "certwatch.db"),
)
MONITOR_EXPIRING_SOON_DAYS = 30
MONITOR_MAX_DOMAINS = 100
MONITOR_CHECK_COOLDOWN_SECONDS = 10  # min gap between checks of the same domain
MONITOR_RATE_LIMIT_REQUESTS = 20  # add/check calls per client per window
MONITOR_RATE_LIMIT_WINDOW_SECONDS = 60
