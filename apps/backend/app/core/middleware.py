"""Request id, security headers and CSRF (double submit on cookie authenticated writes)."""
import secrets
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.errors import error_response, request_id_ctx
from app.core.security import constant_eq

SAFE = {"GET", "HEAD", "OPTIONS"}
CSRF_EXEMPT = ("/api/v1/oauth/token", "/api/v1/oauth/register")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = request.headers.get("x-request-id", "")[:64] or uuid.uuid4().hex
        request_id_ctx.set(rid)
        structlog.contextvars.bind_contextvars(request_id=rid)

        has_cookie = "rsv_access" in request.cookies or "rsv_refresh" in request.cookies
        if (
            request.method not in SAFE and has_cookie
            and not request.headers.get("authorization") and not request.url.path.startswith(CSRF_EXEMPT)
        ):
            cookie, header = request.cookies.get("rsv_csrf", ""), request.headers.get("x-csrf-token", "")
            if not cookie or not constant_eq(cookie, header):
                return error_response(403, "csrf_failed", "Security check failed. Refresh and try again.")

        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers.setdefault("Cache-Control", "no-store")
        if settings.cookie_secure:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        structlog.contextvars.clear_contextvars()
        return response


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)
