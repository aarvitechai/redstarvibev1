import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/avif", "image/gif"}
VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm"}
AUDIO_TYPES = {"audio/webm", "audio/ogg", "audio/mp4"}


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


class TextOverlay(BaseModel):
    """Text shown on top of one photo or video. Stored as data, so it stays sharp and can be moderated."""

    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    x: float = Field(ge=0, le=100)  # centre of the text, percent of the frame
    y: float = Field(ge=0, le=100)
    size: Literal["small", "medium", "large"]
    style: Literal["shadow", "label", "highlight"]
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class MediaEdit(BaseModel):
    """Filter and adjustments, shown with CSS so the original file is never changed."""

    filter: Literal["none", "clarendon", "warm", "cool", "vintage", "mono"]
    brightness: int = Field(ge=50, le=150)
    contrast: int = Field(ge=50, le=150)
    saturate: int = Field(ge=0, le=200)


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
    text_overlay: TextOverlay | None = None
    edit: MediaEdit | None = None
    audio: str | None = None
