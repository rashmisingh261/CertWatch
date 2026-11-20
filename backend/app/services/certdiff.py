"""CertDiff: parse two PEM certificates and compare their attributes.

All parsing is done in memory with ``cryptography``; uploaded content is never written
to disk, executed, or echoed back to the client (only parsed attributes are returned).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Union

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed448, ed25519, rsa

from app.core import config
from app.core.errors import InvalidCertificateError, PayloadTooLargeError
from app.schemas_diff import CertSummary, DiffCounts, DiffResponse, FieldDiff
from app.services.certutil import not_valid_utc, public_key_fingerprint

Value = Union[str, List[str], None]

# (key, label, kind) in display order.
FIELDS: List[Tuple[str, str, str]] = [
    ("subject", "Subject", "scalar"),
    ("issuer", "Issuer", "scalar"),
    ("serial_number", "Serial number", "scalar"),
    ("not_before", "Valid from", "scalar"),
    ("not_after", "Valid until", "scalar"),
    ("signature_algorithm", "Signature algorithm", "scalar"),
    ("public_key_algorithm", "Public key algorithm", "scalar"),
    ("public_key_size", "Public key size (bits)", "scalar"),
    ("public_key_fingerprint", "Public key fingerprint (SHA-256)", "scalar"),
    ("fingerprint_sha256", "Certificate fingerprint (SHA-256)", "scalar"),
    ("sans", "Subject Alternative Names", "list"),
    ("basic_constraints", "Basic Constraints", "scalar"),
    ("key_usage", "Key Usage", "list"),
    ("extended_key_usage", "Extended Key Usage", "list"),
]


# --------------------------------------------------------------------------- parsing
def parse_pem(data: bytes, which: str) -> x509.Certificate:
    """Validate ``data`` is exactly one PEM X.509 certificate. ``which`` is 'A' or 'B'."""
    who = f"Certificate {which}"
    if not data or not data.strip():
        raise InvalidCertificateError(f"{who}: the uploaded file is empty.")
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise PayloadTooLargeError(f"{who}: file exceeds the {config.MAX_UPLOAD_BYTES // 1000} KB limit.")
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        raise InvalidCertificateError(
            f"{who}: not a PEM text file. Binary formats such as DER are not supported; "
            "upload a PEM file (-----BEGIN CERTIFICATE-----)."
        ) from None
    if "PRIVATE KEY-----" in text:
        raise InvalidCertificateError(
            f"{who}: the file contains a private key. Never upload private keys — "
            "upload only the public certificate."
        )
    if "-----BEGIN CERTIFICATE REQUEST-----" in text or "-----BEGIN NEW CERTIFICATE REQUEST-----" in text:
        raise InvalidCertificateError(f"{who}: this is a certificate signing request (CSR), not a certificate.")
    if "-----BEGIN CERTIFICATE-----" not in text:
        raise InvalidCertificateError(f"{who}: no PEM certificate found (expected -----BEGIN CERTIFICATE-----).")
    try:
        certs = x509.load_pem_x509_certificates(data)
    except ValueError:
        raise InvalidCertificateError(
            f"{who}: the PEM data is malformed or is not a valid X.509 certificate."
        ) from None
    if len(certs) != 1:
        raise InvalidCertificateError(
            f"{who}: the file contains {len(certs)} certificates; upload exactly one certificate per file."
        )
    return certs[0]


# ------------------------------------------------------------------------ extraction
def _utc_iso(cert: x509.Certificate, attr: str) -> str:
    return not_valid_utc(cert, attr).isoformat()


def _hex(raw: bytes) -> str:
    return raw.hex(":").upper()


def _key_info(cert: x509.Certificate) -> Tuple[str, Optional[str]]:
    key = cert.public_key()
    if isinstance(key, rsa.RSAPublicKey):
        return "RSA", str(key.key_size)
    if isinstance(key, ec.EllipticCurvePublicKey):
        return f"EC ({key.curve.name})", str(key.curve.key_size)
    if isinstance(key, ed25519.Ed25519PublicKey):
        return "Ed25519", "256"
    if isinstance(key, ed448.Ed448PublicKey):
        return "Ed448", "456"
    if isinstance(key, dsa.DSAPublicKey):
        return "DSA", str(key.key_size)
    return type(key).__name__.replace("PublicKey", ""), None


def _ext(cert: x509.Certificate, cls):
    try:
        return cert.extensions.get_extension_for_class(cls).value
    except x509.ExtensionNotFound:
        return None


def _oid_name(oid: x509.ObjectIdentifier) -> str:
    return getattr(oid, "_name", None) or oid.dotted_string


_KEY_USAGE_FLAGS = [
    "digital_signature", "content_commitment", "key_encipherment", "data_encipherment",
    "key_agreement", "key_cert_sign", "crl_sign",
]


def _san_entries(ext) -> List[str]:
    out: List[str] = []
    for gn in ext:
        if isinstance(gn, x509.DNSName):
            out.append(f"DNS:{gn.value}")
        elif isinstance(gn, x509.IPAddress):
            out.append(f"IP:{gn.value}")
        elif isinstance(gn, x509.RFC822Name):
            out.append(f"email:{gn.value}")
        elif isinstance(gn, x509.UniformResourceIdentifier):
            out.append(f"URI:{gn.value}")
        else:
            out.append(f"{type(gn).__name__}:{gn.value}")
    return sorted(set(out))


def extract(cert: x509.Certificate) -> Dict[str, Value]:
    """Return the comparable attributes. Missing extensions yield None / empty list."""
    try:
        key_algo, key_size = _key_info(cert)

        san = _ext(cert, x509.SubjectAlternativeName)
        bc = _ext(cert, x509.BasicConstraints)
        ku = _ext(cert, x509.KeyUsage)
        eku = _ext(cert, x509.ExtendedKeyUsage)

        key_usage: List[str] = []
        if ku is not None:
            key_usage = [f for f in _KEY_USAGE_FLAGS if getattr(ku, f)]
            if ku.key_agreement:  # encipher_only / decipher_only only defined then
                key_usage += [f for f in ("encipher_only", "decipher_only") if getattr(ku, f)]

        bc_text: Optional[str] = None
        if bc is not None:
            bc_text = f"CA: {'true' if bc.ca else 'false'}"
            if bc.path_length is not None:
                bc_text += f", path length: {bc.path_length}"

        try:
            sig_name = cert.signature_algorithm_oid
            sig = _oid_name(sig_name)
        except Exception:
            sig = "unknown"

        return {
            "subject": cert.subject.rfc4514_string() or "(empty)",
            "issuer": cert.issuer.rfc4514_string() or "(empty)",
            "serial_number": format(cert.serial_number, "X"),
            "not_before": _utc_iso(cert, "not_valid_before"),
            "not_after": _utc_iso(cert, "not_valid_after"),
            "signature_algorithm": sig,
            "public_key_algorithm": key_algo,
            "public_key_size": key_size,
            "public_key_fingerprint": public_key_fingerprint(cert),
            "fingerprint_sha256": _hex(cert.fingerprint(hashes.SHA256())),
            "sans": _san_entries(san) if san is not None else [],
            "basic_constraints": bc_text,
            "key_usage": sorted(key_usage),
            "extended_key_usage": sorted(_oid_name(o) for o in eku) if eku is not None else [],
        }
    except (ValueError, x509.DuplicateExtension, x509.UnsupportedGeneralNameType):
        raise InvalidCertificateError(
            "The certificate could not be fully parsed (malformed extension or unsupported content)."
        ) from None


# ---------------------------------------------------------------------- comparison
def _days_between(a_iso: str, b_iso: str) -> int:
    return round((datetime.fromisoformat(b_iso) - datetime.fromisoformat(a_iso)).total_seconds() / 86400)


def _explain(key: str, label: str, status: str, a: Value, b: Value,
             added: List[str], removed: List[str]) -> str:
    if status == "UNCHANGED":
        if key == "fingerprint_sha256":
            return "Identical: the two files are the same certificate."
        if (a in (None, [], "")) and (b in (None, [], "")):
            return f"{label} is not present in either certificate."
        return "Identical in both certificates."
    if status == "ADDED":
        return f"{label} is present only in Certificate B (Certificate A has none)."
    if status == "REMOVED":
        return f"{label} is present only in Certificate A (Certificate B has none)."

    # MODIFIED
    if key in ("sans", "key_usage", "extended_key_usage"):
        parts = []
        if added:
            parts.append(f"{len(added)} added in B")
        if removed:
            parts.append(f"{len(removed)} removed from A")
        return f"{label} changed: {', '.join(parts)}."
    if key == "not_after" and isinstance(a, str) and isinstance(b, str):
        d = _days_between(a, b)
        shift = f"{abs(d)} day{'s' if abs(d) != 1 else ''}"
        if d > 0:
            return f"Expiry is {shift} later in B — typical of a renewal."
        return f"Expiry is {shift} earlier in B."
    if key == "not_before" and isinstance(a, str) and isinstance(b, str):
        d = _days_between(a, b)
        return f"Validity starts {abs(d)} day{'s' if abs(d) != 1 else ''} {'later' if d > 0 else 'earlier'} in B."
    notes = {
        "subject": (
            "The subject (the identity the certificate describes) differs, "
            "e.g. a different common name or organisation."
        ),
        "issuer": (
            "The certificates were issued by different CAs or intermediates "
            "(common when switching CA or rotating an intermediate)."
        ),
        "serial_number": (
            "Serial numbers are unique per issued certificate, so these are different "
            "issuances (e.g. a renewal or reissue)."
        ),
        "signature_algorithm": "The issuing CA signed the certificates with different algorithms.",
        "public_key_algorithm": "The certificates use different public key types.",
        "public_key_size": "The public keys have different sizes.",
        "public_key_fingerprint": (
            "The public keys differ, so a new key pair was used. If this were the same key, "
            "the fingerprints would match (keys are often reused on renewal)."
        ),
        "fingerprint_sha256": (
            "The certificate fingerprints differ. This is expected whenever any field differs "
            "(for example a routine renewal) and is not by itself a sign of a security problem."
        ),
        "basic_constraints": "Basic Constraints differ (this controls whether the certificate may act as a CA).",
    }
    return notes.get(key, f"{label} differs between the certificates.")


def compare(a: Dict[str, Value], b: Dict[str, Value]) -> List[FieldDiff]:
    out: List[FieldDiff] = []
    for key, label, kind in FIELDS:
        va, vb = a.get(key), b.get(key)
        added: List[str] = []
        removed: List[str] = []
        unchanged: List[str] = []
        if kind == "list":
            sa, sb = set(va or []), set(vb or [])
            added, removed, unchanged = sorted(sb - sa), sorted(sa - sb), sorted(sa & sb)
            if not added and not removed:
                status = "UNCHANGED"
            elif not sa:
                status = "ADDED"
            elif not sb:
                status = "REMOVED"
            else:
                status = "MODIFIED"
        else:
            if va == vb:
                status = "UNCHANGED"
            elif va is None:
                status = "ADDED"
            elif vb is None:
                status = "REMOVED"
            else:
                status = "MODIFIED"
        out.append(FieldDiff(
            key=key, label=label, kind=kind, status=status, a=va, b=vb,
            added=added, removed=removed, unchanged=unchanged,
            explanation=_explain(key, label, status, va, vb, added, removed),
        ))
    return out


def _summary(name: str, attrs: Dict[str, Value]) -> CertSummary:
    return CertSummary(
        filename=name,
        subject=str(attrs["subject"]), issuer=str(attrs["issuer"]),
        serial_number=str(attrs["serial_number"]),
        not_before=str(attrs["not_before"]), not_after=str(attrs["not_after"]),
        fingerprint_sha256=str(attrs["fingerprint_sha256"]),
    )


def _safe_name(name: Optional[str], default: str) -> str:
    """Display-only filename: strip path components and control characters, cap length."""
    base = (name or default).replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(c for c in base if c.isprintable())[:100]
    return cleaned or default


def diff_certificates(
    data_a: bytes, data_b: bytes, name_a: Optional[str] = None, name_b: Optional[str] = None
) -> DiffResponse:
    attrs_a = extract(parse_pem(data_a, "A"))
    attrs_b = extract(parse_pem(data_b, "B"))
    fields = compare(attrs_a, attrs_b)
    counts = DiffCounts()
    for f in fields:
        setattr(counts, f.status, getattr(counts, f.status) + 1)
    return DiffResponse(
        compared_at=datetime.now(timezone.utc).isoformat(),
        certificate_a=_summary(_safe_name(name_a, "certificate-a.pem"), attrs_a),
        certificate_b=_summary(_safe_name(name_b, "certificate-b.pem"), attrs_b),
        summary=counts,
        fields=fields,
    )
