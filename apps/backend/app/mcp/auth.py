"""OAuth 2.1 with PKCE for MCP clients. Users approve scopes on a consent screen in the web app."""
import base64
import hashlib
import json
import secrets
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, Db
from app.core.cache import get_redis
from app.core.config import settings
from app.core.errors import bad_request, not_found
from app.core.rate_limit import ip_limit
from app.core.security import create_mcp_token, hash_token, new_opaque_token
from app.modules.auth.models import OAuthClient
from app.modules.users import repository as users

router = APIRouter(prefix="/oauth", tags=["oauth"])
SCOPES = {"read", "write:drafts", "write:reports"}
ACCESS_HOURS = 1


def issuer(request: Request) -> str:
    if settings.mcp_issuer or settings.public_url:
        return settings.mcp_issuer or settings.public_url
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    return f"{request.headers.get('x-forwarded-proto', request.url.scheme)}://{host}"


def metadata(request: Request) -> dict[str, object]:
    base = issuer(request)
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/api/v1/oauth/authorize",
        "token_endpoint": f"{base}/api/v1/oauth/token",
        "registration_endpoint": f"{base}/api/v1/oauth/register",
        "scopes_supported": sorted(SCOPES),
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
    }


class RegisterIn(BaseModel):
    client_name: str = Field("MCP client", max_length=120)
    redirect_uris: list[str] = Field(min_length=1, max_length=5)


def _valid_redirect(uri: str) -> bool:
    parsed = urlparse(uri)
    if parsed.scheme == "https":
        return True
    return parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}


@router.post("/register", status_code=201)
async def register(data: RegisterIn, s: Db, request: Request) -> dict[str, object]:
    await ip_limit("oauth_register", 20, 3600)(request)
    if not all(_valid_redirect(u) for u in data.redirect_uris):
        raise bad_request("invalid_redirect_uri", "Redirect URIs must be https or localhost")
    client = OAuthClient(client_id=secrets.token_urlsafe(24), client_name=data.client_name, redirect_uris=data.redirect_uris)
    s.add(client)
    await s.commit()
    return {
        "client_id": client.client_id, "client_name": client.client_name, "redirect_uris": client.redirect_uris,
        "token_endpoint_auth_method": "none", "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    }


async def _validated_client(s: AsyncSession, client_id: str, redirect_uri: str) -> OAuthClient:
    client = await s.get(OAuthClient, client_id)
    if client is None or redirect_uri not in client.redirect_uris:
        raise bad_request("invalid_client", "Unknown client or redirect URI")
    return client


def _scopes(scope: str | None) -> list[str]:
    requested = (scope or "read").split()
    if not set(requested) <= SCOPES:
        raise bad_request("invalid_scope", "Unknown scope")
    return requested


@router.get("/authorize", include_in_schema=False)
async def authorize(
    s: Db, client_id: str, redirect_uri: str, code_challenge: str, state: str = "", scope: str | None = None,
    code_challenge_method: str = "S256", response_type: str = "code",
) -> RedirectResponse:
    """Validates, then hands off to the consent page. The redirect URI is checked before any redirect."""
    await _validated_client(s, client_id, redirect_uri)
    if response_type != "code" or code_challenge_method != "S256":
        raise bad_request("unsupported", "Only the code flow with S256 PKCE is supported")
    _scopes(scope)
    query = urlencode({
        "client_id": client_id, "redirect_uri": redirect_uri, "code_challenge": code_challenge,
        "state": state, "scope": scope or "read",
    })
    return RedirectResponse(f"/oauth/consent?{query}", status_code=302)


class ConsentIn(BaseModel):
    client_id: str
    redirect_uri: str
    code_challenge: str = Field(min_length=43, max_length=128)
    state: str = ""
    scope: str = "read"
    approve: bool


class ConsentOut(BaseModel):
    redirect_to: str


class ClientInfo(BaseModel):
    client_name: str


@router.get("/clients/{client_id}", response_model=ClientInfo)
async def client_info(client_id: str, s: Db, _: CurrentUser) -> ClientInfo:
    client = await s.get(OAuthClient, client_id)
    if client is None:
        raise not_found("Client")
    return ClientInfo(client_name=client.client_name)


@router.post("/consent", response_model=ConsentOut)
async def consent(data: ConsentIn, me: CurrentUser, s: Db) -> ConsentOut:
    await _validated_client(s, data.client_id, data.redirect_uri)
    sep = "&" if "?" in data.redirect_uri else "?"
    if not data.approve:
        return ConsentOut(redirect_to=f"{data.redirect_uri}{sep}{urlencode({'error': 'access_denied', 'state': data.state})}")
    scopes = _scopes(data.scope)
    code = secrets.token_urlsafe(32)
    await get_redis().set(f"oauth_code:{hash_token(code)}", json.dumps({
        "user_id": str(me.id), "client_id": data.client_id, "redirect_uri": data.redirect_uri,
        "challenge": data.code_challenge, "scopes": scopes,
    }), ex=300)
    await users.audit(s, me.id, "oauth.consent", data.client_id, None, {"scopes": scopes})
    await s.commit()
    return ConsentOut(redirect_to=f"{data.redirect_uri}{sep}{urlencode({'code': code, 'state': data.state})}")


def _oauth_error(code: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": code}, status_code=status)


def _token_response(user_id: str, scopes: list[str], client_id: str, refresh: str) -> JSONResponse:
    import uuid as _uuid

    return JSONResponse({
        "access_token": create_mcp_token(_uuid.UUID(user_id), scopes, client_id, ACCESS_HOURS),
        "token_type": "Bearer", "expires_in": ACCESS_HOURS * 3600, "scope": " ".join(scopes), "refresh_token": refresh,
    }, headers={"Cache-Control": "no-store"})


@router.post("/token", include_in_schema=False)
async def token(
    request: Request, grant_type: str = Form(), client_id: str = Form(), code: str | None = Form(None),
    redirect_uri: str | None = Form(None), code_verifier: str | None = Form(None), refresh_token: str | None = Form(None),
) -> JSONResponse:
    await ip_limit("oauth_token", 60, 600)(request)
    client = get_redis()
    if grant_type == "authorization_code":
        if not code or not code_verifier:
            return _oauth_error("invalid_request")
        raw = await client.getdel(f"oauth_code:{hash_token(code)}")  # single use
        if raw is None:
            return _oauth_error("invalid_grant")
        grant = json.loads(raw)
        expected = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
        if grant["client_id"] != client_id or grant["redirect_uri"] != redirect_uri or expected != grant["challenge"]:
            return _oauth_error("invalid_grant")
    elif grant_type == "refresh_token":
        if not refresh_token:
            return _oauth_error("invalid_request")
        raw = await client.getdel(f"oauth_refresh:{hash_token(refresh_token)}")  # rotated on use
        if raw is None:
            return _oauth_error("invalid_grant")
        grant = json.loads(raw)
        if grant["client_id"] != client_id:
            return _oauth_error("invalid_grant")
    else:
        return _oauth_error("unsupported_grant_type")
    new_refresh = new_opaque_token()
    await client.set(f"oauth_refresh:{hash_token(new_refresh)}", json.dumps({
        "user_id": grant["user_id"], "client_id": client_id, "scopes": grant["scopes"],
    }), ex=30 * 86400)
    return _token_response(grant["user_id"], grant["scopes"], client_id, new_refresh)
