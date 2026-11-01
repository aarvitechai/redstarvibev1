"""Sign up, email OTP, password and Google login, rotating refresh tokens, TOTP MFA."""
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta

import httpx
import pyotp
from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.core.config import settings
from app.core.errors import AppError, bad_request, conflict, unauthorized
from app.core.events import enqueue
from app.core.ids import uuid7
from app.core.middleware import new_csrf_token
from app.core.rate_limit import check, hit
from app.core.security import (
    constant_eq,
    create_access_token,
    decrypt_field,
    encrypt_field,
    hash_password,
    hash_token,
    is_breached_password,
    new_opaque_token,
    verify_password,
)
from app.modules.auth import repository as repo
from app.modules.auth.models import RefreshToken
from app.modules.auth.schemas import SignupIn
from app.modules.users import repository as users
from app.modules.users.models import Profile, User

OTP_TTL = 600
OTP_ATTEMPTS = 5
MIN_AGE = 13
REUSE_GRACE = timedelta(seconds=10)  # two browser tabs refreshing at once are not an attack


def is_old_enough(dob: date) -> bool:
    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return age >= MIN_AGE


async def verify_turnstile(token: str | None, ip: str) -> None:
    if not settings.turnstile_secret:
        return
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": settings.turnstile_secret, "response": token or "", "remoteip": ip},
        )
    if not resp.json().get("success"):
        raise bad_request("bot_check_failed", "Bot check failed. Please try again.")


async def _send_otp(email: str, purpose: str) -> None:
    code = f"{secrets.randbelow(1_000_000):06d}"
    client = get_redis()
    pipe = client.pipeline()
    pipe.set(f"otp:{purpose}:{email.lower()}", hash_token(code), ex=OTP_TTL)
    pipe.delete(f"otp_tries:{purpose}:{email.lower()}")
    await pipe.execute()
    subject = f"{code} is your RedStarVibe code"
    body = f"Your RedStarVibe verification code is {code}. It expires in 10 minutes.\n\nDid not ask for this? Ignore this email."
    await enqueue("notifications.send_email", email, subject, body)


async def _check_otp(email: str, purpose: str, code: str) -> None:
    client = get_redis()
    key = f"otp:{purpose}:{email.lower()}"
    tries_key = f"otp_tries:{purpose}:{email.lower()}"
    stored = await client.get(key)
    if stored is None:
        raise bad_request("otp_invalid", "That code is wrong or has expired")
    tries = await client.incr(tries_key)
    await client.expire(tries_key, OTP_TTL)
    if tries > OTP_ATTEMPTS:
        await client.delete(key)
        raise bad_request("otp_invalid", "That code is wrong or has expired")
    if not constant_eq(str(stored), hash_token(code)):
        raise bad_request("otp_invalid", "That code is wrong or has expired")
    await client.delete(key, tries_key)


async def signup(s: AsyncSession, data: SignupIn, ip: str) -> None:
    await verify_turnstile(data.turnstile_token, ip)
    if not is_old_enough(data.date_of_birth):
        raise bad_request("too_young", "You must be at least 13 to use RedStarVibe")
    if data.username.lower() in data.password.lower() or await is_breached_password(data.password):
        raise bad_request("weak_password", "This password is too common or has appeared in a data breach")
    taken = await users.by_username(s, data.username)
    existing = await users.by_email(s, data.email)
    if taken and (existing is None or taken.id != existing.id):
        raise conflict("username_taken", "That username is taken")
    if existing and existing.status != "pending":
        # Same response as a new sign up, so this endpoint cannot be used to discover accounts.
        await enqueue(
            "notifications.send_email", data.email, "RedStarVibe sign up attempt",
            "Someone tried to sign up with this email. You already have an account, so just log in.",
        )
        return
    password_hash = hash_password(data.password)
    if existing:
        existing.username, existing.password_hash = data.username, password_hash
        existing.date_of_birth = data.date_of_birth
        existing.profile.display_name = data.display_name or data.username
    else:
        user = User(
            username=data.username, email=data.email, password_hash=password_hash,
            date_of_birth=data.date_of_birth, status="pending",
        )
        await users.add_user(s, user, Profile(display_name=data.display_name or data.username))
    await s.commit()
    await _send_otp(data.email, "verify")


async def resend_verification(s: AsyncSession, email: str) -> None:
    await hit(f"otp_send:{email.lower()}", 3, 600)
    user = await users.by_email(s, email)
    if user and user.status == "pending":
        await _send_otp(email, "verify")


async def verify_email(s: AsyncSession, email: str, code: str) -> User:
    await _check_otp(email, "verify", code)
    user = await users.by_email(s, email)
    if user is None:
        raise bad_request("otp_invalid", "That code is wrong or has expired")
    if user.status == "pending":
        user.status = "active"
        await s.commit()
        await enqueue("users.score_spam", user.id)
    return user


def _check_active(user: User) -> None:
    if user.status == "pending":
        raise AppError(403, "email_unverified", "Please verify your email first")
    if user.status not in {"active", "deleting"}:
        raise AppError(403, "account_suspended", "This account has been suspended")


def _check_totp(user: User, code: str | None) -> None:
    if not user.totp_enabled:
        return
    if not code:
        raise AppError(401, "mfa_required", "Enter the code from your authenticator app")
    secret = decrypt_field(user.totp_secret_encrypted or "")
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        raise AppError(401, "mfa_invalid", "That authenticator code is wrong")


async def password_login(s: AsyncSession, identifier: str, password: str, totp: str | None, ip: str) -> User:
    bucket = f"login:id:{identifier.lower()}"
    await check(bucket, 10, 900)  # only failures count, so normal logins never lock anyone out
    user = await (users.by_email(s, identifier) if "@" in identifier else users.by_username(s, identifier))
    if not verify_password(password, user.password_hash if user else None) or user is None:
        await users.audit(s, user.id if user else None, "auth.login_failed", identifier[:200], ip)
        await s.commit()
        await hit(bucket, 1000, 900)
        raise unauthorized("invalid_credentials", "Wrong username or password")
    _check_active(user)
    _check_totp(user, totp)
    await users.audit(s, user.id, "auth.login", str(user.id), ip)
    return user


async def request_login_otp(s: AsyncSession, email: str) -> None:
    await hit(f"otp_send:{email.lower()}", 3, 600)
    user = await users.by_email(s, email)
    if user and user.status in {"active", "deleting"}:
        await _send_otp(email, "login")


async def otp_login(s: AsyncSession, email: str, code: str, totp: str | None, ip: str) -> User:
    user = await users.by_email(s, email)
    if user is None:
        raise bad_request("otp_invalid", "That code is wrong or has expired")
    _check_active(user)
    if user.totp_enabled and not totp:
        raise AppError(401, "mfa_required", "Enter the code from your authenticator app")
    await _check_otp(email, "login", code)
    _check_totp(user, totp)
    await users.audit(s, user.id, "auth.login_otp", str(user.id), ip)
    return user


# ---- sessions ----
def _set_cookie(resp: Response, name: str, value: str, max_age: int, http_only: bool = True, path: str = "/") -> None:
    resp.set_cookie(
        name, value, max_age=max_age, path=path, httponly=http_only, secure=settings.cookie_secure,
        samesite="lax", domain=settings.cookie_domain or None,
    )


async def start_session(
    s: AsyncSession, resp: Response, user: User, user_agent: str | None, family: uuid.UUID | None = None
) -> None:
    access, _ = create_access_token(user.id, user.role)
    refresh = new_opaque_token()
    await repo.add_refresh(s, RefreshToken(
        user_id=user.id, family_id=family or uuid7(), token_hash=hash_token(refresh),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
        user_agent=(user_agent or "")[:300],
    ))
    await s.commit()
    lifetime = settings.refresh_token_days * 86400
    _set_cookie(resp, "rsv_access", access, settings.access_token_minutes * 60)
    _set_cookie(resp, "rsv_refresh", refresh, lifetime, path="/api/v1/auth")
    _set_cookie(resp, "rsv_csrf", new_csrf_token(), lifetime, http_only=False)


def clear_session(resp: Response) -> None:
    for name, path in (("rsv_access", "/"), ("rsv_refresh", "/api/v1/auth"), ("rsv_csrf", "/")):
        resp.delete_cookie(name, path=path, domain=settings.cookie_domain or None)


async def rotate(s: AsyncSession, resp: Response, token: str | None, user_agent: str | None) -> User:
    if not token:
        raise unauthorized("no_session", "Please log in")
    row = await repo.refresh_by_hash(s, hash_token(token))
    now = datetime.now(UTC)
    if row is None or row.revoked_at or row.expires_at < now:
        raise unauthorized("no_session", "Please log in")
    if row.used_at and now - row.used_at > REUSE_GRACE:
        await repo.revoke_family(s, row.family_id)  # a stolen token was replayed: end every descendant
        await users.audit(s, row.user_id, "auth.refresh_reuse", str(row.family_id))
        await s.commit()
        raise unauthorized("no_session", "Please log in")
    user = await users.by_id(s, row.user_id)
    if user is None or user.status not in {"active", "deleting"}:
        raise unauthorized("no_session", "Please log in")
    row.used_at = row.used_at or now
    await start_session(s, resp, user, user_agent, row.family_id)
    return user


async def logout(s: AsyncSession, refresh: str | None, access_jti: str | None) -> None:
    if refresh:
        row = await repo.refresh_by_hash(s, hash_token(refresh))
        if row:
            await repo.revoke_family(s, row.family_id)
            await s.commit()
    if access_jti:
        await get_redis().set(f"deny:{access_jti}", "1", ex=settings.access_token_minutes * 60)


# ---- TOTP ----
async def totp_setup(s: AsyncSession, user: User) -> tuple[str, str]:
    if user.totp_enabled:
        raise conflict("mfa_already_enabled", "Authenticator app is already on")
    secret = pyotp.random_base32()
    user.totp_secret_encrypted = encrypt_field(secret)
    await s.commit()
    return secret, pyotp.TOTP(secret).provisioning_uri(user.email, issuer_name="RedStarVibe")


async def totp_enable(s: AsyncSession, user: User, code: str) -> None:
    if not user.totp_secret_encrypted:
        raise bad_request("mfa_not_started", "Start setup first")
    if not pyotp.TOTP(decrypt_field(user.totp_secret_encrypted)).verify(code, valid_window=1):
        raise bad_request("mfa_invalid", "That code is wrong")
    user.totp_enabled = True
    await users.audit(s, user.id, "auth.mfa_enabled", str(user.id))
    await s.commit()


async def totp_disable(s: AsyncSession, user: User, code: str) -> None:
    _check_totp(user, code)
    user.totp_enabled, user.totp_secret_encrypted = False, None
    await users.audit(s, user.id, "auth.mfa_disabled", str(user.id))
    await s.commit()


# ---- Google (Authlib, state + PKCE) ----
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"


def _google_client(redirect_uri: str):  # type: ignore[no-untyped-def]
    from authlib.integrations.httpx_client import AsyncOAuth2Client

    return AsyncOAuth2Client(
        settings.google_client_id, settings.google_client_secret,
        scope="openid email profile", redirect_uri=redirect_uri, code_challenge_method="S256",
    )


async def google_start(redirect_uri: str) -> str:
    if not settings.google_client_id:
        raise AppError(503, "not_configured", "Google sign in is not configured")
    verifier = secrets.token_urlsafe(48)
    state = secrets.token_urlsafe(24)
    await get_redis().set(f"oauth_state:{state}", verifier, ex=600)
    client = _google_client(redirect_uri)
    url, _ = client.create_authorization_url(GOOGLE_AUTH, state=state, code_verifier=verifier)
    return str(url)


async def google_finish(s: AsyncSession, code: str, state: str, redirect_uri: str) -> User:
    client_redis = get_redis()
    verifier = await client_redis.getdel(f"oauth_state:{state}")
    if not verifier:
        raise bad_request("oauth_state", "Sign in expired. Please try again.")
    client = _google_client(redirect_uri)
    await client.fetch_token(GOOGLE_TOKEN, code=code, code_verifier=verifier, grant_type="authorization_code")
    info = (await client.get(GOOGLE_USERINFO)).json()
    await client.aclose()
    if not info.get("email_verified"):
        raise bad_request("email_unverified", "Your Google email is not verified")
    user = await repo.by_google_sub(s, info["sub"]) or await users.by_email(s, info["email"])
    if user is None:
        base = "".join(c for c in info["email"].split("@")[0].lower() if c.isalnum() or c in "_.")[:24] or "user"
        username = base if len(base) >= 3 and not await users.by_username(s, base) else f"{base}{secrets.randbelow(10**5)}"
        user = User(username=username, email=info["email"], google_sub=info["sub"], status="active")
        await users.add_user(s, user, Profile(display_name=info.get("name") or username))
    else:
        user.google_sub = user.google_sub or info["sub"]
        if user.status == "pending":
            user.status = "active"
    _check_active(user)
    await s.commit()
    return user


async def confirm_age(s: AsyncSession, user: User, dob: date) -> None:
    if not is_old_enough(dob):
        await users.schedule_deletion(s, user, days=0)
        user.status = "suspended"
        await s.commit()
        raise bad_request("too_young", "You must be at least 13 to use RedStarVibe")
    user.date_of_birth = dob
    await s.commit()
