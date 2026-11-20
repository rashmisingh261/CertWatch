from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import __version__
from app.api.certdiff import router as certdiff_router
from app.api.inspect import router
from app.api.monitor import router as monitor_router
from app.core import config
from app.core.errors import CertWatchError
from app.core.upload_limit import BodySizeLimitMiddleware
from app.db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()  # create the SQLite schema on first start; idempotent
    yield


app = FastAPI(title="CertWatch", version=__version__, lifespan=lifespan)
app.include_router(router)
app.include_router(certdiff_router)
app.include_router(monitor_router)
app.add_middleware(
    BodySizeLimitMiddleware,
    path="/api/certdiff",
    max_bytes=config.MAX_REQUEST_BYTES,
    message=f"Upload too large: each certificate must be under {config.MAX_UPLOAD_BYTES // 1000} KB.",
)


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(CertWatchError)
async def certwatch_error_handler(_: Request, exc: CertWatchError) -> JSONResponse:
    return _error(exc.status_code, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, _: RequestValidationError) -> JSONResponse:
    if request.url.path == "/api/certdiff":
        return _error(422, "invalid_request", "Upload two PEM files as 'certificate_a' and 'certificate_b'.")
    if request.url.path.startswith("/api/monitor"):
        return _error(
            422, "invalid_request", "Invalid request: expected {\"domain\": \"example.com\"} or a numeric id."
        )
    return _error(422, "invalid_request", "Request body must be JSON like {\"domain\": \"example.com\"}.")


@app.exception_handler(Exception)
async def unexpected_handler(_: Request, __: Exception) -> JSONResponse:
    return _error(500, "internal_error", "Unexpected server error.")
