"""Small certificate helpers shared by the Inspector and CertDiff."""
from __future__ import annotations

from datetime import datetime, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization


def not_valid_utc(cert: x509.Certificate, attr: str) -> datetime:
    """``attr`` is 'not_valid_before' or 'not_valid_after'; always timezone-aware UTC."""
    value = getattr(cert, attr + "_utc", None)
    if value is None:  # cryptography < 42
        value = getattr(cert, attr).replace(tzinfo=timezone.utc)
    return value


def public_key_fingerprint(cert: x509.Certificate) -> str:
    """SHA-256 of the SubjectPublicKeyInfo, as upper-case colon-separated hex."""
    spki = cert.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    digest = hashes.Hash(hashes.SHA256())
    digest.update(spki)
    return digest.finalize().hex(":").upper()
