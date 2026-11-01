import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import bad_request, not_found
from app.core.events import enqueue
from app.core.ids import uuid7
from app.core.rate_limit import hit
from app.core.storage import presign_put, public_url
from app.modules.media import repository as repo
from app.modules.media.models import MediaAsset
from app.modules.media.schemas import IMAGE_TYPES, VIDEO_TYPES, AssetOut, ImageVariant, UploadIn, UploadOut
from app.modules.users.models import User


async def create_upload(s: AsyncSession, user: User, data: UploadIn, origin: str) -> UploadOut:
    await hit(f"upload:user:{user.id}", 120, 3600)
    if data.content_type in IMAGE_TYPES:
        kind, limit = "image", settings.max_image_bytes
    elif data.content_type in VIDEO_TYPES and data.purpose != "avatar":
        kind, limit = "video", settings.max_video_bytes
    else:
        raise bad_request("unsupported_type", "That file type is not supported")
    if data.size > limit:
        raise bad_request("file_too_large", f"That file is too large. The limit is {limit // (1024 * 1024)} MB.")
    if data.purpose == "reel" and kind != "video":
        raise bad_request("reel_needs_video", "A reel must be a video")
    asset_id = uuid7()
    key = f"{user.id}/{asset_id}"
    await repo.add(s, MediaAsset(
        id=asset_id, owner_id=user.id, purpose=data.purpose, kind=kind, raw_key=key,
        declared_type=data.content_type, size_bytes=data.size,
    ))
    await s.commit()
    url = presign_put(key, data.content_type, data.size, origin)
    return UploadOut(asset_id=asset_id, upload_url=url, headers={"Content-Type": data.content_type})


def asset_out(asset: MediaAsset, alt_text: str | None = None) -> AssetOut:
    v = asset.variants or {}
    return AssetOut(
        id=asset.id, kind=asset.kind, status=asset.status, error=asset.error, width=asset.width, height=asset.height,
        duration=asset.duration, placeholder=asset.placeholder, alt_text=alt_text,
        images=[
            ImageVariant(w=i["w"], avif=public_url(i.get("avif")), webp=public_url(i["webp"]) or "")
            for i in v.get("images", [])
        ],
        hls=public_url(v.get("hls")), poster=public_url(v.get("poster")), subtitles=public_url(v.get("vtt")),
    )


async def complete(s: AsyncSession, user: User, asset_id: uuid.UUID) -> AssetOut:
    asset = await repo.get(s, asset_id)
    if asset is None or asset.owner_id != user.id:
        raise not_found("Upload")
    if asset.status == "pending":
        await enqueue("media.process_asset", asset.id, queue="media")
    return asset_out(asset)


async def get_owned(s: AsyncSession, user: User, asset_id: uuid.UUID) -> AssetOut:
    asset = await repo.get(s, asset_id)
    if asset is None or asset.owner_id != user.id:
        raise not_found("Upload")
    return asset_out(asset)
