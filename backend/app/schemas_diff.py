from __future__ import annotations

from typing import List, Union

from pydantic import BaseModel

Value = Union[str, List[str], None]


class CertSummary(BaseModel):
    filename: str
    subject: str
    issuer: str
    serial_number: str
    not_before: str
    not_after: str
    fingerprint_sha256: str


class FieldDiff(BaseModel):
    key: str
    label: str
    kind: str  # "scalar" | "list"
    status: str  # UNCHANGED | MODIFIED | ADDED | REMOVED
    a: Value = None
    b: Value = None
    added: List[str] = []  # list fields: present only in B
    removed: List[str] = []  # list fields: present only in A
    unchanged: List[str] = []  # list fields: present in both
    explanation: str


class DiffCounts(BaseModel):
    UNCHANGED: int = 0
    MODIFIED: int = 0
    ADDED: int = 0
    REMOVED: int = 0


class DiffResponse(BaseModel):
    compared_at: str  # ISO 8601 UTC
    certificate_a: CertSummary
    certificate_b: CertSummary
    summary: DiffCounts
    fields: List[FieldDiff]
