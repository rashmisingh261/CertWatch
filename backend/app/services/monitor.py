"""Certificate Monitor: persistence + check pipeline + status logic.

STATUS RULES (first match wins) -- evaluated when a check completes:

  1. CHECK_FAILED   the check itself failed (DNS, connect, timeout, TLS handshake)
  2. EXPIRED        certificate is past its expiry date
  3. INVALID        chain not trusted, hostname mismatch, or not yet valid
  4. CHANGED        fingerprint differs from the previous *successful* observation
  5. EXPIRING_SOON  30 days or less remaining
  6. HEALTHY        otherwise (valid, trusted, hostname matches, > 30 days remaining)

Because time passes between checks, statuses are also *aged* when read
(``effective_status``): a stored HEALTHY becomes EXPIRING_SOON, and any stored
non-failure status becomes EXPIRED, once the stored expiry date requires it.
CHECK_FAILED is never aged -- it describes our most recent attempt.

Changes are descriptive, not verdicts: a changed fingerprint is normal on renewal.
History is append-only: a change adds an observation; the previous one is kept.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core import config
from app.core.errors import (
    CertWatchError,
    DuplicateDomainError,
    MonitorLimitError,
    NotFoundError,
    RateLimitedError,
)
from app.core.validation import validate_domain
from app.db import connect, transaction
from app.schemas import InspectResponse
from app.schemas_monitor import (
    ChangeSet,
    FieldChange,
    MonitoredDomain,
    MonitoredDomainDetail,
    ObservationOut,
)
from app.services.runner import run_inspection

HEALTHY = "HEALTHY"
EXPIRING_SOON = "EXPIRING_SOON"
EXPIRED = "EXPIRED"
INVALID = "INVALID"
CHECK_FAILED = "CHECK_FAILED"
CHANGED = "CHANGED"

# Failures on *add* that mean "don't save this": a blocked/private target, a name that
# doesn't resolve (almost certainly a typo), or the server being too busy to even try.
# Other failures (connect/timeout/TLS) are saved as CHECK_FAILED: the host exists.
NOT_SAVED_ON_ADD = {"blocked_address", "dns_error", "busy"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


# ----------------------------------------------------------------------- status logic
def expiry_status(not_after: datetime, now: datetime) -> str:
    remaining = not_after - now
    if remaining < timedelta(0):
        return EXPIRED
    if remaining <= timedelta(days=config.MONITOR_EXPIRING_SOON_DAYS):
        return EXPIRING_SOON
    return HEALTHY


def status_for_report(report: InspectResponse, changed: bool, now: datetime) -> str:
    base = expiry_status(_parse(report.validity.not_after), now)
    if base == EXPIRED:
        return EXPIRED
    v = report.validation
    if not v.trusted or not v.hostname_match or report.validity.not_yet_valid:
        return INVALID
    if changed:
        return CHANGED
    return base


def effective_status(stored: str, not_after: Optional[str], now: datetime) -> str:
    if stored == CHECK_FAILED or not not_after:
        return stored
    na = _parse(not_after)
    if na < now:
        return EXPIRED
    if stored == HEALTHY:
        return expiry_status(na, now)
    return stored


def days_remaining(not_after: Optional[str], now: datetime) -> Optional[int]:
    if not not_after:
        return None
    return int((_parse(not_after) - now).total_seconds() // 86400)


# --------------------------------------------------------------------- change detection
_TRACKED = [
    ("subject", "Subject"),
    ("issuer", "Issuer"),
    ("serial_number", "Serial number"),
    ("not_before", "Valid from"),
    ("not_after", "Valid until"),
    ("signature_algorithm", "Signature algorithm"),
    ("public_key", "Public key"),
    ("public_key_fingerprint", "Public key fingerprint"),
]


def _view_from_report(r: InspectResponse) -> Dict[str, Any]:
    return {
        "subject": r.subject.rfc4514,
        "issuer": r.issuer.rfc4514,
        "serial_number": r.serial_number,
        "not_before": r.validity.not_before,
        "not_after": r.validity.not_after,
        "signature_algorithm": r.signature_algorithm,
        "public_key": r.public_key,
        "public_key_fingerprint": r.public_key_fingerprint,
        "sans": sorted(r.sans),
    }


def _view_from_row(row: sqlite3.Row) -> Dict[str, Any]:
    view = {k: row[k] for k, _ in _TRACKED}
    view["sans"] = sorted(json.loads(row["sans"] or "[]"))
    return view


def detect_changes(prev: Dict[str, Any], cur: Dict[str, Any]) -> ChangeSet:
    """Describe exactly what differs. Neutral wording: renewals are routine."""
    fields = [
        FieldChange(key=k, label=label, before=prev.get(k), after=cur.get(k))
        for k, label in _TRACKED
        if prev.get(k) != cur.get(k)
    ]
    keys = {f.key for f in fields}
    sp, sc = set(prev["sans"]), set(cur["sans"])

    if "issuer" in keys:
        hint = ("Issued by a different CA. This is expected if you switched CA; "
                "otherwise it is worth verifying.")
    elif "public_key_fingerprint" in keys:
        hint = "Same issuer but a new public key, typical of a renewal that also rotated the key."
    elif keys or sp != sc:
        hint = "Same issuer and public key, consistent with a routine renewal or reissue."
    else:
        hint = "The certificate was replaced but none of the tracked attributes differ."
    return ChangeSet(fields=fields, sans_added=sorted(sc - sp), sans_removed=sorted(sp - sc), hint=hint)


# ------------------------------------------------------------------------- persistence
def _issuer_display(r: InspectResponse) -> str:
    return r.issuer.common_name or r.issuer.organization or r.issuer.rfc4514


def _record(
    conn: sqlite3.Connection,
    domain_id: int,
    report: Optional[InspectResponse],
    error: Optional[CertWatchError],
    now: datetime,
) -> None:
    """Append an observation and update the domain snapshot. Call inside a transaction."""
    row = conn.execute("SELECT id FROM monitored_domains WHERE id = ?", (domain_id,)).fetchone()
    if row is None:
        raise NotFoundError("Monitored domain not found.")
    ts = now.isoformat()

    if report is None:
        assert error is not None
        conn.execute(
            "INSERT INTO observations (domain_id, observed_at, outcome, status, error_code, error_message) "
            "VALUES (?, ?, 'failed', ?, ?, ?)",
            (domain_id, ts, CHECK_FAILED, error.code, error.message),
        )
        conn.execute(
            "UPDATE monitored_domains SET status = ?, last_checked_at = ?, last_error = ? WHERE id = ?",
            (CHECK_FAILED, ts, error.message, domain_id),
        )
        return  # last known certificate details are deliberately kept

    prev = conn.execute(
        "SELECT * FROM observations WHERE domain_id = ? AND outcome = 'ok' ORDER BY id DESC LIMIT 1",
        (domain_id,),
    ).fetchone()
    changed = prev is not None and prev["fingerprint_sha256"] != report.fingerprint_sha256
    changes = detect_changes(_view_from_row(prev), _view_from_report(report)) if changed else None
    status = status_for_report(report, changed, now)
    v = report.validation

    conn.execute(
        """INSERT INTO observations
           (domain_id, observed_at, outcome, status, ip_address, fingerprint_sha256,
            public_key_fingerprint, issuer, subject, serial_number, not_before, not_after,
            tls_version, signature_algorithm, public_key, sans, trusted, trust_error,
            hostname_match, changed, changes)
           VALUES (?, ?, 'ok', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            domain_id, ts, status, report.ip_address, report.fingerprint_sha256,
            report.public_key_fingerprint, report.issuer.rfc4514, report.subject.rfc4514,
            report.serial_number, report.validity.not_before, report.validity.not_after,
            report.tls_version, report.signature_algorithm, report.public_key,
            json.dumps(report.sans), int(v.trusted), v.trust_error, int(v.hostname_match),
            int(changed), changes.model_dump_json() if changes else None,
        ),
    )
    conn.execute(
        """UPDATE monitored_domains SET status = ?, last_checked_at = ?, last_error = NULL,
           not_after = ?, fingerprint_sha256 = ?, issuer = ?, tls_version = ?,
           last_changed_at = CASE WHEN ? THEN ? ELSE last_changed_at END
           WHERE id = ?""",
        (
            status, ts, report.validity.not_after, report.fingerprint_sha256,
            _issuer_display(report), report.tls_version, int(changed), ts, domain_id,
        ),
    )


def _summary(row: sqlite3.Row, now: datetime) -> Dict[str, Any]:
    return dict(
        id=row["id"], domain=row["domain"], added_at=row["added_at"],
        last_checked_at=row["last_checked_at"], last_changed_at=row["last_changed_at"],
        status=effective_status(row["status"], row["not_after"], now),
        issuer=row["issuer"], not_after=row["not_after"],
        days_remaining=days_remaining(row["not_after"], now),
        fingerprint_sha256=row["fingerprint_sha256"], tls_version=row["tls_version"],
        last_error=row["last_error"],
    )


def _observation_out(row: sqlite3.Row) -> ObservationOut:
    def flag(v):
        return None if v is None else bool(v)

    return ObservationOut(
        id=row["id"], observed_at=row["observed_at"], outcome=row["outcome"], status=row["status"],
        ip_address=row["ip_address"], fingerprint_sha256=row["fingerprint_sha256"],
        issuer=row["issuer"], subject=row["subject"], serial_number=row["serial_number"],
        not_before=row["not_before"], not_after=row["not_after"], tls_version=row["tls_version"],
        signature_algorithm=row["signature_algorithm"], public_key=row["public_key"],
        sans=json.loads(row["sans"] or "[]"), trusted=flag(row["trusted"]),
        trust_error=row["trust_error"], hostname_match=flag(row["hostname_match"]),
        changed=bool(row["changed"]),
        changes=ChangeSet.model_validate_json(row["changes"]) if row["changes"] else None,
        error_code=row["error_code"], error_message=row["error_message"],
    )


# ---------------------------------------------------------------------------- service
def _inspect(domain: str) -> Tuple[Optional[InspectResponse], Optional[CertWatchError]]:
    """Run the Phase 1 inspection (validation, SSRF guards, port 443, timeouts)."""
    try:
        return run_inspection(domain), None
    except CertWatchError as exc:
        return None, exc


def list_domains() -> List[MonitoredDomain]:
    now = now_utc()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM monitored_domains ORDER BY domain COLLATE NOCASE").fetchall()
    return [MonitoredDomain(**_summary(r, now)) for r in rows]


def get_detail(domain_id: int) -> MonitoredDomainDetail:
    now = now_utc()
    with connect() as conn:
        row = conn.execute("SELECT * FROM monitored_domains WHERE id = ?", (domain_id,)).fetchone()
        if row is None:
            raise NotFoundError("Monitored domain not found.")
        obs = conn.execute(
            "SELECT * FROM observations WHERE domain_id = ? ORDER BY id DESC", (domain_id,)
        ).fetchall()
    return MonitoredDomainDetail(**_summary(row, now), observations=[_observation_out(o) for o in obs])


def add_domain(raw_domain: str) -> MonitoredDomainDetail:
    domain = validate_domain(raw_domain)  # normalised: lower-case, punycode
    with connect() as conn:  # cheap checks first: no outbound connection for duplicates
        if conn.execute("SELECT 1 FROM monitored_domains WHERE domain = ?", (domain,)).fetchone():
            raise DuplicateDomainError(f"'{domain}' is already being monitored.")
        count = conn.execute("SELECT COUNT(*) FROM monitored_domains").fetchone()[0]
        if count >= config.MONITOR_MAX_DOMAINS:
            raise MonitorLimitError(
                f"Limit reached: at most {config.MONITOR_MAX_DOMAINS} domains can be monitored."
            )

    report, error = _inspect(domain)
    if error is not None and error.code in NOT_SAVED_ON_ADD:
        raise error

    now = now_utc()
    with connect() as conn, transaction(conn):
        try:
            cur = conn.execute(
                "INSERT INTO monitored_domains (domain, added_at, status) VALUES (?, ?, ?)",
                (domain, now.isoformat(), CHECK_FAILED),
            )
        except sqlite3.IntegrityError:  # lost a race with a concurrent add
            raise DuplicateDomainError(f"'{domain}' is already being monitored.") from None
        domain_id = cur.lastrowid
        _record(conn, domain_id, report, error, now)
    return get_detail(domain_id)


def check_domain(domain_id: int) -> MonitoredDomainDetail:
    with connect() as conn:
        row = conn.execute("SELECT * FROM monitored_domains WHERE id = ?", (domain_id,)).fetchone()
    if row is None:
        raise NotFoundError("Monitored domain not found.")

    if row["last_checked_at"]:
        age = (now_utc() - _parse(row["last_checked_at"])).total_seconds()
        wait = config.MONITOR_CHECK_COOLDOWN_SECONDS - age
        if wait > 0:
            raise RateLimitedError(
                f"'{row['domain']}' was checked moments ago. Please wait {int(wait) + 1}s."
            )

    report, error = _inspect(row["domain"])  # re-validated + SSRF-checked on every check
    now = now_utc()
    with connect() as conn, transaction(conn):
        _record(conn, domain_id, report, error, now)
    return get_detail(domain_id)


def delete_domain(domain_id: int) -> None:
    with connect() as conn:
        cur = conn.execute("DELETE FROM monitored_domains WHERE id = ?", (domain_id,))
        if cur.rowcount == 0:
            raise NotFoundError("Monitored domain not found.")
