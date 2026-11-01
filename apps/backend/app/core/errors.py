"""Consistent error body: {"error": {"code", "message", "request_id"}}."""
from contextvars import ContextVar

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
log = structlog.get_logger()


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def not_found(what: str = "Resource") -> AppError:
    return AppError(404, "not_found", f"{what} not found")


def forbidden(message: str = "You do not have access to this") -> AppError:
    return AppError(403, "forbidden", message)


def bad_request(code: str, message: str) -> AppError:
    return AppError(400, code, message)


def conflict(code: str, message: str) -> AppError:
    return AppError(409, code, message)


def unauthorized(code: str = "unauthorized", message: str = "Please log in") -> AppError:
    return AppError(401, code, message)


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "request_id": request_id_ctx.get()}},
    )


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return error_response(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        return error_response(422, "validation_error", f"{field}: {first.get('msg', 'invalid')}".strip(": "))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", exc_info=exc)
        return error_response(500, "internal_error", "Something went wrong")
