"""AI suggestions for the composer. When AI is off these answer "disabled", never an error."""
import json
import uuid
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import writing
from app.ai.embeddings.search import is_enabled as semantic_enabled
from app.core.cache import get_redis
from app.core.config import settings
from app.core.errors import not_found
from app.core.rate_limit import hit
from app.modules.assistant.service import consume_quota
from app.modules.media import repository as media_repo
from app.modules.users.models import User

CAPTION_SECONDS = 3600


class Features(BaseModel):
    semantic_search: bool
    writing: bool
    captions: bool


class CaptionsOut(BaseModel):
    status: Literal["disabled", "pending", "ready", "failed"]
    captions: list[str] = []
    tagline: str | None = None
    hashtags: list[str] = []


class RewriteIn(BaseModel):
    text: str = Field(min_length=1, max_length=2200)
    style: Literal["fun", "short", "hinglish"]


class RewriteOut(BaseModel):
    status: Literal["disabled", "ready", "failed"]
    text: str | None = None


class HashtagsIn(BaseModel):
    text: str = Field(min_length=1, max_length=2200)


class HashtagsOut(BaseModel):
    status: Literal["disabled", "ready", "failed"]
    hashtags: list[str] = []


def caption_key(asset_id: uuid.UUID | str) -> str:
    return f"ai:captions:{asset_id}"


async def store_captions(asset_id: uuid.UUID, result: dict[str, object] | None) -> None:
    value = {"status": "ready", **result} if result else {"status": "failed"}
    await get_redis().set(caption_key(asset_id), json.dumps(value), ex=CAPTION_SECONDS)


def features() -> Features:
    return Features(semantic_search=semantic_enabled(), writing=writing.text_enabled(), captions=writing.captions_enabled())


async def captions(s: AsyncSession, user: User, asset_id: uuid.UUID) -> CaptionsOut:
    asset = await media_repo.get(s, asset_id)
    if asset is None or asset.owner_id != user.id:
        raise not_found("Upload")
    if not writing.captions_enabled():
        return CaptionsOut(status="disabled")
    stored = await get_redis().get(caption_key(asset_id))
    return CaptionsOut(**json.loads(stored)) if stored else CaptionsOut(status="pending")


async def _guard(user: User, name: str) -> None:
    await hit(f"{name}:user:{user.id}", 20, 3600)  # one person cannot keep the CPU busy
    if settings.ai_provider == "anthropic":
        await consume_quota(user)


async def rewrite(user: User, data: RewriteIn) -> RewriteOut:
    if not writing.text_enabled():
        return RewriteOut(status="disabled")
    await _guard(user, "rewrite")
    text = await writing.rewrite(data.text, data.style)
    return RewriteOut(status="ready", text=text) if text else RewriteOut(status="failed")


async def hashtags(user: User, data: HashtagsIn) -> HashtagsOut:
    if not writing.text_enabled():
        return HashtagsOut(status="disabled")
    await _guard(user, "hashtags")
    tags = await writing.hashtags_for(data.text)
    return HashtagsOut(status="ready", hashtags=tags) if tags else HashtagsOut(status="failed")
