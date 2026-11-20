import datetime as dt

import pytest
from cryptography.hazmat.primitives import serialization

from app.core.errors import InvalidCertificateError, PayloadTooLargeError
from app.services.certdiff import diff_certificates, parse_pem
from tests.certgen import NOW, make_pem, new_ec_key, new_rsa_key, private_key_pem


def fields(res):
    return {f.key: f for f in res.fields}


def test_identical_certificates_all_unchanged():
    pem = make_pem(sans=["example.com"], ca=False, key_usage=True, eku=True)
    res = diff_certificates(pem, pem)
    assert all(f.status == "UNCHANGED" for f in res.fields)
    assert res.summary.UNCHANGED == len(res.fields) and res.summary.MODIFIED == 0
    assert "same certificate" in fields(res)["fingerprint_sha256"].explanation


def test_different_issuers():
    key = new_ec_key()
    res = diff_certificates(make_pem(key=key, issuer_cn="CA One"), make_pem(key=key, issuer_cn="CA Two"))
    f = fields(res)
    assert f["issuer"].status == "MODIFIED"
    assert "CN=CA One" in f["issuer"].a and "CN=CA Two" in f["issuer"].b
    assert f["subject"].status == "UNCHANGED"
    # same key reused, different certificate: key fingerprint equal, cert fingerprint differs
    assert f["public_key_fingerprint"].status == "UNCHANGED"
    assert f["fingerprint_sha256"].status == "MODIFIED"
    assert "not by itself a sign of a security problem" in f["fingerprint_sha256"].explanation


def test_different_validity_periods():
    key = new_ec_key()
    a = make_pem(key=key)
    b = make_pem(
        key=key,
        not_before=NOW + dt.timedelta(days=60),
        not_after=NOW + dt.timedelta(days=150),
    )
    f = fields(diff_certificates(a, b))
    assert f["not_before"].status == "MODIFIED" and f["not_after"].status == "MODIFIED"
    assert "60 days later" in f["not_after"].explanation
    assert "renewal" in f["not_after"].explanation


def test_different_public_keys():
    f = fields(diff_certificates(make_pem(key=new_ec_key()), make_pem(key=new_rsa_key(2048))))
    assert f["public_key_algorithm"].status == "MODIFIED"
    assert f["public_key_algorithm"].a.startswith("EC") and f["public_key_algorithm"].b == "RSA"
    assert f["public_key_size"].a == "256" and f["public_key_size"].b == "2048"
    assert f["public_key_fingerprint"].status == "MODIFIED"


def test_same_algorithm_different_key_modified_fingerprint_only():
    f = fields(diff_certificates(make_pem(key=new_ec_key()), make_pem(key=new_ec_key())))
    assert f["public_key_algorithm"].status == "UNCHANGED"
    assert f["public_key_fingerprint"].status == "MODIFIED"


def test_san_added_and_removed():
    key = new_ec_key()
    a = make_pem(key=key, sans=["example.com", "www.example.com"])
    b = make_pem(key=key, sans=["example.com", "api.example.com"])
    san = fields(diff_certificates(a, b))["sans"]
    assert san.status == "MODIFIED"
    assert san.unchanged == ["DNS:example.com"]
    assert san.removed == ["DNS:www.example.com"]
    assert san.added == ["DNS:api.example.com"]
    assert "1 added in B" in san.explanation and "1 removed from A" in san.explanation


def test_san_only_added_entries():
    a = make_pem(sans=["example.com"])
    b = make_pem(sans=["example.com", "api.example.com"])
    san = fields(diff_certificates(a, b))["sans"]
    assert san.status == "MODIFIED" and san.added == ["DNS:api.example.com"] and san.removed == []


def test_san_extension_missing_in_one_cert():
    a = make_pem(sans=None)
    b = make_pem(sans=["example.com"])
    san = fields(diff_certificates(a, b))["sans"]
    assert san.status == "ADDED" and san.added == ["DNS:example.com"]
    san_rev = fields(diff_certificates(b, a))["sans"]
    assert san_rev.status == "REMOVED" and san_rev.removed == ["DNS:example.com"]


def test_missing_optional_extensions_handled():
    res = diff_certificates(make_pem(), make_pem())  # no SAN/BC/KU/EKU at all
    f = fields(res)
    assert f["sans"].status == "UNCHANGED" and f["sans"].a == []
    assert f["basic_constraints"].status == "UNCHANGED" and f["basic_constraints"].a is None
    assert f["key_usage"].a == [] and f["extended_key_usage"].a == []
    assert "not present in either" in f["basic_constraints"].explanation


def test_extensions_present_in_one_only():
    f = fields(diff_certificates(make_pem(), make_pem(ca=True, key_usage=True, eku=True)))
    assert f["basic_constraints"].status == "ADDED" and f["basic_constraints"].b == "CA: true"
    assert f["key_usage"].status == "ADDED"
    assert f["key_usage"].added == ["digital_signature", "key_encipherment"]
    assert f["extended_key_usage"].added == ["clientAuth", "serverAuth"]


def test_serial_and_signature_fields():
    f = fields(diff_certificates(make_pem(serial=255), make_pem(serial=256)))
    assert f["serial_number"].a == "FF" and f["serial_number"].b == "100"
    assert f["serial_number"].status == "MODIFIED"
    assert f["signature_algorithm"].a == "ecdsa-with-SHA256"


# ---------------------------------------------------------------- invalid input
def test_empty_file():
    with pytest.raises(InvalidCertificateError, match="Certificate A.*empty"):
        parse_pem(b"", "A")
    with pytest.raises(InvalidCertificateError, match="empty"):
        parse_pem(b"  \n ", "B")


def test_garbage_text():
    with pytest.raises(InvalidCertificateError, match="no PEM certificate"):
        parse_pem(b"hello world", "A")


def test_malformed_pem_body():
    bad = b"-----BEGIN CERTIFICATE-----\nnot base64 at all!!\n-----END CERTIFICATE-----\n"
    with pytest.raises(InvalidCertificateError, match="malformed"):
        parse_pem(bad, "B")


def test_truncated_pem():
    pem = make_pem()
    with pytest.raises(InvalidCertificateError):
        parse_pem(pem[: len(pem) // 2], "A")


def test_binary_der_rejected():
    from cryptography import x509
    der = x509.load_pem_x509_certificate(make_pem()).public_bytes(serialization.Encoding.DER)
    with pytest.raises(InvalidCertificateError, match="PEM"):
        parse_pem(der, "A")


def test_private_key_rejected():
    with pytest.raises(InvalidCertificateError, match="private key"):
        parse_pem(private_key_pem(), "A")
    # even bundled with a certificate
    with pytest.raises(InvalidCertificateError, match="private key"):
        parse_pem(make_pem() + private_key_pem(), "B")


def test_multiple_certs_rejected():
    with pytest.raises(InvalidCertificateError, match="2 certificates"):
        parse_pem(make_pem() + make_pem(serial=2), "A")


def test_csr_rejected():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    key = new_ec_key()
    csr = x509.CertificateSigningRequestBuilder().subject_name(x509.Name([])).sign(key, hashes.SHA256())
    with pytest.raises(InvalidCertificateError, match="signing request"):
        parse_pem(csr.public_bytes(serialization.Encoding.PEM), "A")


def test_oversized_rejected():
    from app.core import config
    with pytest.raises(PayloadTooLargeError):
        parse_pem(b"A" * (config.MAX_UPLOAD_BYTES + 1), "A")


def test_filename_sanitised():
    pem = make_pem()
    res = diff_certificates(pem, pem, "../../etc/passwd\x00.pem", None)
    assert res.certificate_a.filename == "passwd.pem"
    assert res.certificate_b.filename == "certificate-b.pem"
