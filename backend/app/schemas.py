from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class InspectRequest(BaseModel):
    domain: str = Field(..., max_length=300)


class Name(BaseModel):
    rfc4514: str
    common_name: Optional[str] = None
    organization: Optional[str] = None


class Validity(BaseModel):
    not_before: str  # ISO 8601 UTC
    not_after: str
    days_remaining: int  # negative when expired
    expired: bool
    not_yet_valid: bool


class Validation(BaseModel):
    """Result of verification. Inspection can succeed while these are False."""

    trusted: bool  # chain verifies against the CA bundle (and is within validity)
    trust_error: Optional[str] = None
    trust_error_code: Optional[int] = None
    hostname_match: bool
    hostname_detail: str


class InspectResponse(BaseModel):
    domain: str
    ip_address: str
    tls_version: str
    cipher: Optional[str] = None
    subject: Name
    issuer: Name
    validity: Validity
    sans: List[str]
    fingerprint_sha256: str
    serial_number: str
    signature_algorithm: Optional[str] = None
    public_key: str
    public_key_fingerprint: Optional[str] = None  # SHA-256 of SubjectPublicKeyInfo
    validation: Validation
    status: str  # "valid" | "expiring_soon" | "expired" | "untrusted" | "hostname_mismatch"
    warnings: List[str] = []


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
