"""SQLite access (stdlib ``sqlite3``; no ORM). One short-lived connection per operation."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.core import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS monitored_domains (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    domain             TEXT NOT NULL UNIQUE,
    added_at           TEXT NOT NULL,
    last_checked_at    TEXT,
    last_changed_at    TEXT,
    status             TEXT NOT NULL,
    not_after          TEXT,
    fingerprint_sha256 TEXT,
    issuer             TEXT,
    tls_version        TEXT,
    last_error         TEXT
);

-- Append-only history: one row per check. Parsed attributes only: no PEM/DER, no keys.
CREATE TABLE IF NOT EXISTS observations (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id              INTEGER NOT NULL REFERENCES monitored_domains(id) ON DELETE CASCADE,
    observed_at            TEXT NOT NULL,
    outcome                TEXT NOT NULL CHECK (outcome IN ('ok', 'failed')),
    status                 TEXT NOT NULL,
    ip_address             TEXT,
    fingerprint_sha256     TEXT,
    public_key_fingerprint TEXT,
    issuer                 TEXT,
    subject                TEXT,
    serial_number          TEXT,
    not_before             TEXT,
    not_after              TEXT,
    tls_version            TEXT,
    signature_algorithm    TEXT,
    public_key             TEXT,
    sans                   TEXT,      -- JSON array
    trusted                INTEGER,
    trust_error            TEXT,
    hostname_match         INTEGER,
    changed                INTEGER NOT NULL DEFAULT 0,
    changes                TEXT,      -- JSON: what differed from the previous successful observation
    error_code             TEXT,
    error_message          TEXT
);
CREATE INDEX IF NOT EXISTS idx_observations_domain ON observations(domain_id, id DESC);
"""


def _open() -> sqlite3.Connection:
    path = Path(config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None -> autocommit; transactions are explicit (see ``transaction``).
    conn = sqlite3.connect(str(path), timeout=5, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # required for ON DELETE CASCADE
    return conn


def init_db() -> None:
    """Create tables if needed. Safe to call repeatedly."""
    conn = _open()
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
    finally:
        conn.close()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = _open()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """BEGIN IMMEDIATE takes the write lock up-front so read-then-write is race-free."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
