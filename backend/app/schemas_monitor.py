from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class AddDomainRequest(BaseModel):
    domain: str = Field(..., max_length=300)


class FieldChange(BaseModel):
    key: str
    label: str
    before: Optional[str] = None
    after: Optional[str] = None


class ChangeSet(BaseModel):
    """What differed from the previous successful observation (descriptive, not a verdict)."""

    fields: List[FieldChange] = []
    sans_added: List[str] = []
    sans_removed: List[str] = []
    hint: str


class ObservationOut(BaseModel):
    id: int
    observed_at: str
    outcome: str  # "ok" | "failed"
    status: str  # status as computed at the time of the check
    ip_address: Optional[str] = None
    fingerprint_sha256: Optional[str] = None
    issuer: Optional[str] = None
    subject: Optional[str] = None
    serial_number: Optional[str] = None
    not_before: Optional[str] = None
    not_after: Optional[str] = None
    tls_version: Optional[str] = None
    signature_algorithm: Optional[str] = None
    public_key: Optional[str] = None
    sans: List[str] = []
    trusted: Optional[bool] = None
    trust_error: Optional[str] = None
    hostname_match: Optional[bool] = None
    changed: bool = False
    changes: Optional[ChangeSet] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class MonitoredDomain(BaseModel):
    id: int
    domain: str
    added_at: str
    last_checked_at: Optional[str] = None
    last_changed_at: Optional[str] = None
    status: str  # effective status (aged to "now"); see services/monitor.py
    issuer: Optional[str] = None
    not_after: Optional[str] = None
    days_remaining: Optional[int] = None  # negative once expired
    fingerprint_sha256: Optional[str] = None
    tls_version: Optional[str] = None
    last_error: Optional[str] = None


class MonitoredDomainDetail(MonitoredDomain):
    observations: List[ObservationOut] = []  # newest first
