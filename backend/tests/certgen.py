"""Generate throwaway certificates for CertDiff tests (never real certificates)."""
from __future__ import annotations

import datetime as dt
from typing import List, Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

NOW = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


def new_ec_key():
    return ec.generate_private_key(ec.SECP256R1())


def new_rsa_key(bits: int = 2048):
    return rsa.generate_private_key(public_exponent=65537, key_size=bits)


def make_pem(
    *,
    cn: str = "example.com",
    issuer_cn: str = "Test CA",
    sans: Optional[List[str]] = None,
    key=None,
    serial: int = 1000,
    not_before: dt.datetime = NOW,
    not_after: dt.datetime = NOW + dt.timedelta(days=90),
    ca: Optional[bool] = None,
    key_usage: bool = False,
    eku: bool = False,
) -> bytes:
    key = key or new_ec_key()
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer_cn)])
    b = (
        x509.CertificateBuilder()
        .subject_name(subject).issuer_name(issuer)
        .public_key(key.public_key()).serial_number(serial)
        .not_valid_before(not_before).not_valid_after(not_after)
    )
    if sans is not None:
        b = b.add_extension(x509.SubjectAlternativeName([x509.DNSName(s) for s in sans]), False)
    if ca is not None:
        b = b.add_extension(x509.BasicConstraints(ca=ca, path_length=None), True)
    if key_usage:
        b = b.add_extension(
            x509.KeyUsage(True, False, True, False, False, False, False, False, False), True
        )
    if eku:
        b = b.add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]),
            False,
        )
    return b.sign(key, hashes.SHA256()).public_bytes(serialization.Encoding.PEM)


def private_key_pem() -> bytes:
    return new_ec_key().private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
