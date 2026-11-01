"""Auth and session dependencies."""
import uuid
from typing import Annotated

import jwt
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.core.config import settings
from app.core.database import get_session
from app.core.errors import AppError, forbidden, unauthorized
from app.core.rate_limit import client_ip
from app.core.security import decode_token
from app.modules.users.models import User

Db = Annotated[AsyncSession, Depends(get_session)]


async def _token_user_id(request: Request) -> uuid.UUID | None:
    token = request.cookies.get("rsv_access")
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:]
    if not token:
        return None
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise unauthorized("token_expired", "Session expired") from exc
    except jwt.InvalidTokenError as exc:
        raise unauthorized("invalid_token", "Invalid session") from exc
    if await get_redis().exists(f"deny:{payload.get('jti')}"):
        raise unauthorized("token_revoked", "Session ended")
    return uuid.UUID(str(payload["sub"]))


async def current_user(request: Request, session: Db) -> User:
    uid = await _token_user_id(request)
    if uid is None:
        raise unauthorized()
    user = await session.get(User, uid)
    if user is None or user.status not in {"active", "deleting"}:
        raise unauthorized("account_inactive", "This account is not active")
    return user


async def optional_user(request: Request, session: Db) -> User | None:
    try:
        return await current_user(request, session)
    except AppError as exc:
        if exc.code == "unauthorized":
            return None
        if exc.code == "token_expired":  # let the client refresh instead of showing an anonymous page
            raise
        return None


async def admin_user(request: Request, user: Annotated[User, Depends(current_user)]) -> User:
    allow = [ip.strip() for ip in settings.admin_ip_allowlist.split(",") if ip.strip()]
    if allow and client_ip(request) not in allow:
        raise forbidden("Admin access is not allowed from this network")
    if user.role != "admin":
        raise forbidden("Admin access required")
    if settings.is_prod and not user.totp_enabled:
        raise forbidden("Admins must enable MFA")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
OptionalUser = Annotated[User | None, Depends(optional_user)]
AdminUser = Annotated[User, Depends(admin_user)]
