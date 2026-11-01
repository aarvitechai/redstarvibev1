from urllib.parse import urljoin

import jwt
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse

from app.api.deps import CurrentUser, Db
from app.core.config import settings
from app.core.rate_limit import client_ip, ip_limit
from app.core.security import decode_token
from app.modules.auth import schemas, service
from app.modules.users import service as users
from app.modules.users.schemas import MeOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _origin(request: Request) -> str:
    if settings.public_url:
        return settings.public_url
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    return f"{request.headers.get('x-forwarded-proto', request.url.scheme)}://{host}"


@router.get("/providers", response_model=schemas.Providers)
async def providers() -> schemas.Providers:
    return schemas.Providers(
        google=bool(settings.google_client_id), turnstile_site_key=settings.turnstile_site_key or None
    )


@router.post("/signup", status_code=202, response_model=schemas.Accepted,
             dependencies=[Depends(ip_limit("signup", 10, 3600))])
async def signup(data: schemas.SignupIn, request: Request, s: Db) -> schemas.Accepted:
    await service.signup(s, data, client_ip(request))
    return schemas.Accepted(detail="Check your email for a 6 digit code")


@router.post("/verify-email", response_model=MeOut, dependencies=[Depends(ip_limit("verify", 30, 600))])
async def verify_email(data: schemas.VerifyIn, request: Request, response: Response, s: Db) -> MeOut:
    user = await service.verify_email(s, data.email, data.code)
    await service.start_session(s, response, user, request.headers.get("user-agent"))
    return await users.me_out(s, user)


@router.post("/resend-otp", status_code=202, response_model=schemas.Accepted,
             dependencies=[Depends(ip_limit("otp", 20, 3600))])
async def resend(data: schemas.EmailIn, s: Db) -> schemas.Accepted:
    await service.resend_verification(s, data.email)
    return schemas.Accepted(detail="If that account needs verifying, a new code is on its way")


@router.post("/login", response_model=MeOut, dependencies=[Depends(ip_limit("login", 100, 600))])
async def login(data: schemas.LoginIn, request: Request, response: Response, s: Db) -> MeOut:
    user = await service.password_login(s, data.identifier, data.password, data.totp_code, client_ip(request))
    await service.start_session(s, response, user, request.headers.get("user-agent"))
    return await users.me_out(s, user)


@router.post("/otp/request", status_code=202, response_model=schemas.Accepted,
             dependencies=[Depends(ip_limit("otp", 20, 3600))])
async def otp_request(data: schemas.EmailIn, s: Db) -> schemas.Accepted:
    await service.request_login_otp(s, data.email)
    return schemas.Accepted(detail="If that account exists, a code is on its way")


@router.post("/otp/login", response_model=MeOut, dependencies=[Depends(ip_limit("verify", 30, 600))])
async def otp_login(data: schemas.OtpLoginIn, request: Request, response: Response, s: Db) -> MeOut:
    user = await service.otp_login(s, data.email, data.code, data.totp_code, client_ip(request))
    await service.start_session(s, response, user, request.headers.get("user-agent"))
    return await users.me_out(s, user)


@router.post("/refresh", response_model=MeOut, dependencies=[Depends(ip_limit("refresh", 120, 600))])
async def refresh(request: Request, response: Response, s: Db) -> MeOut:
    user = await service.rotate(s, response, request.cookies.get("rsv_refresh"), request.headers.get("user-agent"))
    return await users.me_out(s, user)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, s: Db) -> None:
    jti = None
    if access := request.cookies.get("rsv_access"):
        try:
            jti = str(decode_token(access).get("jti"))
        except jwt.InvalidTokenError:
            jti = None
    await service.logout(s, request.cookies.get("rsv_refresh"), jti)
    service.clear_session(response)


@router.get("/me", response_model=MeOut)
async def me(user: CurrentUser, s: Db) -> MeOut:
    return await users.me_out(s, user)


@router.post("/age", status_code=204)
async def age(data: schemas.AgeIn, user: CurrentUser, s: Db) -> None:
    await service.confirm_age(s, user, data.date_of_birth)


@router.post("/mfa/totp/setup", response_model=schemas.TotpSetup)
async def totp_setup(user: CurrentUser, s: Db) -> schemas.TotpSetup:
    secret, uri = await service.totp_setup(s, user)
    return schemas.TotpSetup(secret=secret, otpauth_uri=uri)


@router.post("/mfa/totp/enable", status_code=204)
async def totp_enable(data: schemas.TotpCode, user: CurrentUser, s: Db) -> None:
    await service.totp_enable(s, user, data.code)


@router.post("/mfa/totp/disable", status_code=204)
async def totp_disable(data: schemas.TotpCode, user: CurrentUser, s: Db) -> None:
    await service.totp_disable(s, user, data.code)


@router.get("/google/login", include_in_schema=False)
async def google_login(request: Request) -> RedirectResponse:
    return RedirectResponse(await service.google_start(urljoin(_origin(request), "/api/v1/auth/google/callback")))


@router.get("/google/callback", include_in_schema=False)
async def google_callback(code: str, state: str, request: Request, s: Db) -> Response:
    uri = urljoin(_origin(request), "/api/v1/auth/google/callback")
    user = await service.google_finish(s, code, state, uri)
    response = RedirectResponse("/feed" if user.date_of_birth else "/age-check", status_code=302)
    await service.start_session(s, response, user, request.headers.get("user-agent"))
    return response
