"""RFC 9457 problem-details error handling.

Domain exceptions are typed; this module maps them to HTTP centrally so
routers and services never construct HTTP responses themselves.
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ForgeError(Exception):
    """Base for all domain errors."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    title = "Internal error"

    def __init__(self, detail: str = "") -> None:
        self.detail = detail
        super().__init__(detail)


class NotFoundError(ForgeError):
    status_code = status.HTTP_404_NOT_FOUND
    title = "Not found"


class ConflictError(ForgeError):
    status_code = status.HTTP_409_CONFLICT
    title = "Conflict"


class ValidationFailedError(ForgeError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    title = "Validation failed"


class UpstreamError(ForgeError):
    """An external provider (LLM, embeddings, source) failed."""

    status_code = status.HTTP_502_BAD_GATEWAY
    title = "Upstream provider error"


def _problem(status_code: int, title: str, detail: str, instance: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "type": "about:blank",
            "title": title,
            "status": status_code,
            "detail": detail,
            "instance": instance,
        },
        media_type="application/problem+json",
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ForgeError)
    async def forge_error_handler(request: Request, exc: ForgeError) -> JSONResponse:
        return _problem(exc.status_code, exc.title, exc.detail, str(request.url.path))

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _problem(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Validation failed",
            str(exc.errors()),
            str(request.url.path),
        )
