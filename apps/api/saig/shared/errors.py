from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from saig.shared.middleware import get_request_id

ERROR_BASE = "https://saig.dev/errors"


class AppError(Exception):
    """Base for expected application failures, rendered as RFC 7807 problem+json."""

    status_code = 500
    error_type = "internal"
    title = "Internal error"

    def __init__(self, detail: str | None = None, extra: dict[str, Any] | None = None):
        self.detail = detail
        self.extra = extra or {}
        super().__init__(detail or self.title)


class UnauthorizedError(AppError):
    status_code = 401
    error_type = "unauthorized"
    title = "Authentication required"


class TokenExpiredError(UnauthorizedError):
    error_type = "token_expired"
    title = "Access token expired"


class ForbiddenError(AppError):
    status_code = 403
    error_type = "forbidden"
    title = "Insufficient permissions"


class NotFoundError(AppError):
    status_code = 404
    error_type = "not_found"
    title = "Resource not found"


class ConflictError(AppError):
    status_code = 409
    error_type = "conflict"
    title = "Conflict"


class DomainError(AppError):
    status_code = 422
    error_type = "domain_rule"
    title = "Business rule violated"


class AccountLockedError(AppError):
    status_code = 423
    error_type = "account_locked"
    title = "Account temporarily locked"


class RateLimitedError(AppError):
    status_code = 429
    error_type = "rate_limited"
    title = "Too many requests"


def _problem(request: Request, status: int, type_slug: str, title: str,
             detail: str | None, extra: dict[str, Any] | None = None) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"{ERROR_BASE}/{type_slug}",
        "title": title,
        "status": status,
        "instance": str(request.url.path),
        "requestId": get_request_id(),
    }
    if detail:
        body["detail"] = detail
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status, content=body,
                        media_type="application/problem+json")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return _problem(request, exc.status_code, exc.error_type, exc.title, exc.detail, exc.extra)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"path": ".".join(str(p) for p in e["loc"][1:]) or str(e["loc"][0]),
             "message": e["msg"]}
            for e in exc.errors()
        ]
        return _problem(request, 422, "validation", "Validation failed",
                        "One or more fields are invalid.", {"errors": errors})

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        # Never leak internals; the request id links to server logs.
        return _problem(request, 500, "internal", "Internal error",
                        "An unexpected error occurred.")
