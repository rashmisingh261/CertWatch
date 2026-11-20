from __future__ import annotations

from fastapi import APIRouter, File, Request, UploadFile

from app.core import config
from app.core.errors import InvalidCertificateError, PayloadTooLargeError
from app.core.rate_limit import limiter
from app.schemas_diff import DiffResponse
from app.services.certdiff import diff_certificates

router = APIRouter(prefix="/api")


async def _read(upload: UploadFile, which: str) -> bytes:
    # Read one byte past the limit so oversize files are detected without loading them fully.
    data = await upload.read(config.MAX_UPLOAD_BYTES + 1)
    await upload.close()
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise PayloadTooLargeError(
            f"Certificate {which}: file exceeds the {config.MAX_UPLOAD_BYTES // 1000} KB limit."
        )
    return data


@router.post("/certdiff", response_model=DiffResponse)
async def certdiff(
    request: Request,
    certificate_a: UploadFile = File(...),
    certificate_b: UploadFile = File(...),
) -> DiffResponse:
    """Compare two uploaded PEM certificates. Nothing is stored."""
    limiter.check(request.client.host if request.client else "unknown")
    data_a = await _read(certificate_a, "A")
    data_b = await _read(certificate_b, "B")
    if not data_a and not data_b:
        raise InvalidCertificateError("Both uploaded files are empty.")
    return diff_certificates(data_a, data_b, certificate_a.filename, certificate_b.filename)
