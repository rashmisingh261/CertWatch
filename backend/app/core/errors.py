"""Domain errors. Each carries a stable machine code, a safe message and an HTTP status."""
from __future__ import annotations


class CertWatchError(Exception):
    code = "internal_error"
    status_code = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InvalidDomainError(CertWatchError):
    code = "invalid_domain"
    status_code = 422


class BlockedAddressError(CertWatchError):
    code = "blocked_address"
    status_code = 403


class DnsResolutionError(CertWatchError):
    code = "dns_error"
    status_code = 502


class ConnectionFailedError(CertWatchError):
    code = "connection_failed"
    status_code = 502


class InspectionTimeoutError(CertWatchError):
    code = "timeout"
    status_code = 504


class TlsHandshakeError(CertWatchError):
    code = "tls_error"
    status_code = 502


class RateLimitedError(CertWatchError):
    code = "rate_limited"
    status_code = 429


class BusyError(CertWatchError):
    code = "busy"
    status_code = 503


class InvalidCertificateError(CertWatchError):
    code = "invalid_certificate"
    status_code = 422


class PayloadTooLargeError(CertWatchError):
    code = "file_too_large"
    status_code = 413


class NotFoundError(CertWatchError):
    code = "not_found"
    status_code = 404


class DuplicateDomainError(CertWatchError):
    code = "duplicate_domain"
    status_code = 409


class MonitorLimitError(CertWatchError):
    code = "limit_reached"
    status_code = 409
