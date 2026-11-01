import uuid
from typing import Literal

from pydantic import BaseModel, Field

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/avif", "image/gif"}
VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm"}


class UploadIn(BaseModel):
    filename: str = Field(max_length=255)
    content_type: str = Field(max_length=100)
    size: int = Field(gt=0)
    purpose: Literal["post", "reel", "story", "avatar", "message"]


class UploadOut(BaseModel):
    asset_id: uuid.UUID
    upload_url: str
    headers: dict[str, str]


class ImageVariant(BaseModel):
    w: int
    avif: str | None = None
    webp: str


class AssetOut(BaseModel):
    id: uuid.UUID
    kind: str
    status: str
    error: str | None = None
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    placeholder: str | None = None
    images: list[ImageVariant] = []
    hls: str | None = None
    poster: str | None = None
    subtitles: str | None = None
    alt_text: str | None = None
