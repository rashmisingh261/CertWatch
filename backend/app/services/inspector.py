"""TLS certificate inspection.

Inspection is distinct from validation:

1. We connect to a pre-validated public IP (no re-resolution; see network_guard).
2. First handshake uses ``CERT_REQUIRED`` against the certifi CA bundle. If it succeeds
   the chain is trusted. If it fails with a certificate verification error we record the
   reason and do a *second* handshake with verification off, ONLY to read the certificate
   for display. The result is then explicitly reported as ``trusted = False``.
3. Hostname matching is computed separately from the SANs so it is reported
   independently of chain trust.
"""
from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import certifi
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed448, ed25519, rsa
from cryptography.x509.oid import NameOID

from app.core import config
from app.core.errors import (
    ConnectionFailedError,
    InspectionTimeoutError,
    TlsHandshakeError,
)
from app.core.network_guard import ResolvedAddress, resolve_public_addresses
from app.core.validation import validate_domain
from app.schemas import InspectResponse, Name, Validation, Validity
from app.services.certutil import not_valid_utc, public_key_fingerprint
from app.services.hostname import hostname_matches

EXPIRING_SOON_DAYS = 30


@dataclass
class _Handshake:
    der: bytes
    tls_version: str
    cipher: Optional[str]
    verify_error: Optional[str]
    verify_code: Optional[int]


def _context(verify: bool) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    # Hostname is checked by us (hostname.py) so chain trust and hostname match
    # can be reported separately. Chain verification itself is never skipped for the
    # trust handshake.
    ctx.check_hostname = False
    if verify:
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.load_verify_locations(cafile=certifi.where())
    else:
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _handshake(addr: ResolvedAddress, host: str, verify: bool) -> _Handshake:
    sock = socket.socket(addr.family, socket.SOCK_STREAM)
    try:
        sock.settimeout(config.CONNECT_TIMEOUT_SECONDS)
        sock.connect((addr.ip, config.TLS_PORT))
        sock.settimeout(config.HANDSHAKE_TIMEOUT_SECONDS)
        # SNI uses the original hostname; the TCP connection goes to the pinned IP.
        with _context(verify).wrap_socket(sock, server_hostname=host) as tls:
            der = tls.getpeercert(binary_form=True)
            if not der:
                raise TlsHandshakeError("Server did not present a certificate.")
            cipher = tls.cipher()
            return _Handshake(
                der=der,
                tls_version=tls.version() or "unknown",
                cipher=cipher[0] if cipher else None,
                verify_error=None,
                verify_code=None,
            )
    finally:
        sock.close()


def _fetch(addr: ResolvedAddress, host: str) -> _Handshake:
    try:
        return _handshake(addr, host, verify=True)
    except ssl.SSLCertVerificationError as exc:
        reason, code = exc.verify_message or str(exc), exc.verify_code
    # Verification failed: fetch the cert for display only, flagged as untrusted.
    hs = _handshake(addr, host, verify=False)
    hs.verify_error, hs.verify_code = reason, code
    return hs


def _first(name: x509.Name, oid) -> Optional[str]:
    attrs = name.get_attributes_for_oid(oid)
    return str(attrs[0].value) if attrs else None


def _name(name: x509.Name) -> Name:
    return Name(
        rfc4514=name.rfc4514_string(),
        common_name=_first(name, NameOID.COMMON_NAME),
        organization=_first(name, NameOID.ORGANIZATION_NAME),
    )


def _public_key_desc(cert: x509.Certificate) -> str:
    key = cert.public_key()
    if isinstance(key, rsa.RSAPublicKey):
        return f"RSA {key.key_size}"
    if isinstance(key, ec.EllipticCurvePublicKey):
        return f"EC {key.curve.name}"
    if isinstance(key, ed25519.Ed25519PublicKey):
        return "Ed25519"
    if isinstance(key, ed448.Ed448PublicKey):
        return "Ed448"
    if isinstance(key, dsa.DSAPublicKey):
        return f"DSA {key.key_size}"
    return type(key).__name__


def _sans(cert: x509.Certificate) -> Tuple[List[str], List[str]]:
    """Return (dns_names, all_display_entries)."""
    try:
        ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return [], []
    dns = ext.get_values_for_type(x509.DNSName)
    ips = [str(i) for i in ext.get_values_for_type(x509.IPAddress)]
    return dns, dns + ips


def build_report(
    host: str, ip: str, hs: _Handshake, now: Optional[datetime] = None
) -> InspectResponse:
    """Pure function: turn handshake data into the API response (unit-testable)."""
    now = now or datetime.now(timezone.utc)
    cert = x509.load_der_x509_certificate(hs.der)
    not_before, not_after = not_valid_utc(cert, "not_valid_before"), not_valid_utc(cert, "not_valid_after")
    seconds_left = (not_after - now).total_seconds()
    days = int(seconds_left // 86400)  # floor; negative once expired
    expired, not_yet = seconds_left < 0, now < not_before

    dns_names, all_sans = _sans(cert)
    host_ok = hostname_matches(host, dns_names)
    if host_ok:
        detail = f"'{host}' matches the certificate's Subject Alternative Names."
    elif not dns_names:
        detail = "Certificate has no DNS Subject Alternative Names."
    else:
        detail = f"'{host}' is not covered by the certificate's Subject Alternative Names."

    trusted = hs.verify_error is None
    warnings: List[str] = []
    if not_yet:
        warnings.append("Certificate is not yet valid.")
    if hs.tls_version in ("TLSv1", "TLSv1.1"):
        warnings.append(f"Deprecated protocol version {hs.tls_version}.")

    if expired:
        status = "expired"
    elif not trusted or not_yet:
        status = "untrusted"
    elif not host_ok:
        status = "hostname_mismatch"
    elif days < EXPIRING_SOON_DAYS:
        status = "expiring_soon"
    else:
        status = "valid"

    try:
        sig = cert.signature_hash_algorithm.name if cert.signature_hash_algorithm else None
    except Exception:  # unsupported hash
        sig = None

    return InspectResponse(
        domain=host,
        ip_address=ip,
        tls_version=hs.tls_version,
        cipher=hs.cipher,
        subject=_name(cert.subject),
        issuer=_name(cert.issuer),
        validity=Validity(
            not_before=not_before.isoformat(),
            not_after=not_after.isoformat(),
            days_remaining=days,
            expired=expired,
            not_yet_valid=not_yet,
        ),
        sans=all_sans,
        fingerprint_sha256=cert.fingerprint(hashes.SHA256()).hex(":").upper(),
        serial_number=format(cert.serial_number, "X"),
        signature_algorithm=sig,
        public_key=_public_key_desc(cert),
        public_key_fingerprint=public_key_fingerprint(cert),
        validation=Validation(
            trusted=trusted,
            trust_error=hs.verify_error,
            trust_error_code=hs.verify_code,
            hostname_match=host_ok,
            hostname_detail=detail,
        ),
        status=status,
        warnings=warnings,
    )


def inspect_domain(raw_domain: str) -> InspectResponse:
    host = validate_domain(raw_domain)
    addresses = resolve_public_addresses(host)[: config.MAX_ADDRESSES_TRIED]

    last_exc: Optional[Exception] = None
    for addr in addresses:
        try:
            hs = _fetch(addr, host)
            try:
                return build_report(host, addr.ip, hs)
            except (ValueError, x509.DuplicateExtension, x509.UnsupportedGeneralNameType):
                # A hostile or broken server can present a certificate we cannot parse.
                raise TlsHandshakeError(
                    "The server presented a certificate that could not be parsed."
                ) from None
        except socket.timeout:
            last_exc = InspectionTimeoutError("Connection to the server timed out.")
        except (ConnectionRefusedError, ConnectionResetError, OSError) as exc:
            if isinstance(exc, ssl.SSLError):
                last_exc = TlsHandshakeError(
                    "TLS handshake failed; the server may not support TLS 1.2+ on port 443."
                )
            else:
                last_exc = ConnectionFailedError(
                    "Could not connect to the server on port 443."
                )
        except TlsHandshakeError as exc:
            last_exc = exc
    assert last_exc is not None
    raise last_exc
