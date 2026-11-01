import re
from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.]{3,30}$")
RESERVED = {
    "admin", "api", "login", "signup", "feed", "explore", "reels", "messages", "notifications", "settings",
    "search", "p", "call", "live", "saved", "new", "oauth", "age-check", "ai", "offline", "redstarvibe", "support",
}


class SignupIn(BaseModel):
    email: EmailStr
    username: str
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field("", max_length=80)
    date_of_birth: date
    turnstile_token: str | None = None

    @field_validator("username")
    @classmethod
    def valid_username(cls, v: str) -> str:
        if not USERNAME_RE.match(v) or v.lower() in RESERVED or v.startswith(".") or v.endswith("."):
            raise ValueError("use 3-30 letters, numbers, _ or . (some names are reserved)")
        return v


class VerifyIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class EmailIn(BaseModel):
    email: EmailStr


class LoginIn(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)
    password: str = Field(max_length=128)
    totp_code: str | None = Field(None, max_length=8)


class OtpLoginIn(VerifyIn):
    totp_code: str | None = Field(None, max_length=8)


class Accepted(BaseModel):
    detail: str


class TotpSetup(BaseModel):
    secret: str
    otpauth_uri: str


class TotpCode(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class AgeIn(BaseModel):
    date_of_birth: date


class Providers(BaseModel):
    google: bool
    turnstile_site_key: str | None = None
