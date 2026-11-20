from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.rate_limit import limiter
from app.schemas import ErrorResponse, InspectRequest, InspectResponse
from app.services.runner import run_inspection

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post(
    "/inspect",
    response_model=InspectResponse,
    responses={
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
)
def inspect(body: InspectRequest, request: Request) -> InspectResponse:
    """Inspect the TLS certificate served by ``domain`` on port 443."""
    limiter.check(request.client.host if request.client else "unknown")
    return run_inspection(body.domain)
