"""Argon2id hashing, JWT, token hashing, field level encryption, breached password check."""
import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet

from app.core.config import settings

_hasher = PasswordHasher()
# Verified against when the account does not exist, so login timing does not reveal accounts.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))
COMMON_PASSWORDS = {
    "password12", "1234567890", "qwertyuiop", "password123", "iloveyou12", "admin12345",
    "welcome123", "letmein123", "qwerty1234", "1q2w3e4r5t", "abcdefghij", "1111111111",
}


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, stored: str | None) -> bool:
    try:
        return _hasher.verify(stored or _DUMMY_HASH, password) and stored is not None
    except (VerificationError, InvalidHashError):
        return False


async def is_breached_password(password: str) -> bool:
    """HaveIBeenPwned k-anonymity: only 5 hash characters leave the server. Fails open."""
    if password.lower() in COMMON_PASSWORDS:
        return True
    if not settings.breached_password_check:
        return False
    digest = hashlib.sha1(password.encode(), usedforsecurity=False).hexdigest().upper()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"https://api.pwnedpasswords.com/range/{digest[:5]}")
        return resp.status_code == 200 and digest[5:] in resp.text
    except httpx.HTTPError:
        return False


def create_access_token(user_id: uuid.UUID, role: str = "user") -> tuple[str, str]:
    now = datetime.now(UTC)
    jti = secrets.token_hex(8)
    token = jwt.encode(
        {"sub": str(user_id), "role": role, "jti": jti, "typ": "access", "iat": now,
         "exp": now + timedelta(minutes=settings.access_token_minutes)},
        settings.jwt_secret, algorithm="HS256",
    )
    return token, jti


def create_mcp_token(user_id: uuid.UUID, scopes: list[str], client_id: str, hours: int = 1) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(user_id), "scope": " ".join(scopes), "client_id": client_id, "typ": "mcp", "aud": "mcp",
         "iat": now, "exp": now + timedelta(hours=hours)},
        settings.jwt_secret, algorithm="HS256",
    )


def decode_token(token: str, typ: str = "access") -> dict[str, object]:
    audience = "mcp" if typ == "mcp" else None
    payload: dict[str, object] = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], audience=audience)
    if payload.get("typ") != typ:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


def new_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def constant_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def _fernet() -> Fernet:
    key = settings.field_encryption_key
    if not key:  # local only; production refuses to start without a key
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.jwt_secret.encode()).digest()).decode()
    return Fernet(key)


def encrypt_field(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_field(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()
