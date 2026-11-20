from __future__ import annotations

from typing import List

from fastapi import APIRouter, Request, Response

from app.core.rate_limit import monitor_limiter
from app.schemas import ErrorResponse
from app.schemas_monitor import AddDomainRequest, MonitoredDomain, MonitoredDomainDetail
from app.services import monitor

router = APIRouter(prefix="/api/monitor")

_ERRORS = {
    403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 409: {"model": ErrorResponse},
    422: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 502: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("", response_model=MonitoredDomainDetail, status_code=201, responses=_ERRORS)
def add_domain(body: AddDomainRequest, request: Request) -> MonitoredDomainDetail:
    """Validate, run a first check, and start monitoring a domain."""
    monitor_limiter.check(_client(request))
    return monitor.add_domain(body.domain)


@router.get("", response_model=List[MonitoredDomain])
def list_domains() -> List[MonitoredDomain]:
    return monitor.list_domains()


@router.get("/{domain_id}", response_model=MonitoredDomainDetail, responses=_ERRORS)
def get_domain(domain_id: int) -> MonitoredDomainDetail:
    return monitor.get_detail(domain_id)


@router.post("/{domain_id}/check", response_model=MonitoredDomainDetail, responses=_ERRORS)
def check_domain(domain_id: int, request: Request) -> MonitoredDomainDetail:
    """Run a manual check now (rate-limited; per-domain cooldown applies)."""
    monitor_limiter.check(_client(request))
    return monitor.check_domain(domain_id)


@router.delete("/{domain_id}", status_code=204, responses=_ERRORS)
def delete_domain(domain_id: int) -> Response:
    monitor.delete_domain(domain_id)
    return Response(status_code=204)
