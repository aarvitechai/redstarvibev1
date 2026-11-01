"""Opaque cursors. Never offset on large tables."""
import base64
from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel

from app.core.errors import bad_request

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None


def encode_cursor(*parts: object) -> str:
    text = "|".join(p.isoformat() if isinstance(p, datetime) else str(p) for p in parts)
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> list[str]:
    try:
        return base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode().split("|")
    except ValueError as exc:
        raise bad_request("invalid_cursor", "Invalid cursor") from exc


def id_cursor(cursor: str | None) -> UUID | None:
    """Cursor over a UUIDv7 primary key, which is time ordered."""
    if not cursor:
        return None
    try:
        return UUID(decode_cursor(cursor)[0])
    except ValueError as exc:
        raise bad_request("invalid_cursor", "Invalid cursor") from exc
