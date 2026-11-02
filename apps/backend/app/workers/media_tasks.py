"""Media pipeline: validate by magic bytes, strip metadata, re-encode, scan, publish to the public bucket."""
import hashlib
import json
import shutil
import socket
import struct
import subprocess  # noqa: S404
import tempfile
import uuid
from pathlib import Path
from typing import Any

import structlog
from botocore.exceptions import ClientError
from PIL import Image, ImageOps, UnidentifiedImageError

from app import models  # noqa: F401
from app.ai.writing import captions_enabled
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.events import enqueue
from app.core.storage import internal
from app.modules.media import repository as repo
from app.modules.media.models import MediaAsset
from app.modules.notifications.service import notify
from app.modules.posts import repository as post_repo
from app.modules.posts import service as posts
from app.workers.celery_app import celery
from app.workers.runtime import run

log = structlog.get_logger()
Image.MAX_IMAGE_PIXELS = 60_000_000  # refuse decompression bombs
WIDTHS = (320, 640, 1080)
LADDER = ((360, "800k", "96k"), (720, "2500k", "128k"), (1080, "5000k", "160k"))
LONG_CACHE = "public, max-age=31536000, immutable"
PURPOSE_SECONDS = {"reel": "max_reel_seconds", "story": "max_reel_seconds"}


class Rejected(Exception):
    """The upload is invalid. Permanent, so never retried."""


def sniff(head: bytes) -> str | None:
    """Type from magic bytes, never from the extension or the declared type."""
    if head[:3] == b"\xff\xd8\xff":
        return "image"
    if head[:8] == b"\x89PNG\r\n\x1a\n" or head[:6] in {b"GIF87a", b"GIF89a"}:
        return "image"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image"
    if head[4:8] == b"ftyp":
        return "image" if head[8:12] in {b"avif", b"avis", b"heic", b"mif1"} else "video"
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return "video"
    return None


def audio_container_ok(head: bytes) -> bool:
    """WebM and MP4 can hold video too, so `process_audio` still refuses any file with a real video track."""
    return head[:4] == b"OggS" or head[:4] == b"\x1a\x45\xdf\xa3" or head[4:8] == b"ftyp" and sniff(head) == "video"


def clamav_clean(path: Path) -> bool:
    """clamd INSTREAM. Scanning is skipped only when CLAMAV_HOST is not configured."""
    if not settings.clamav_host:
        return True
    with socket.create_connection((settings.clamav_host, settings.clamav_port), timeout=60) as sock:
        sock.sendall(b"zINSTREAM\0")
        with path.open("rb") as handle:
            while chunk := handle.read(1 << 16):
                sock.sendall(struct.pack("!L", len(chunk)) + chunk)
        sock.sendall(struct.pack("!L", 0))
        return b"FOUND" not in sock.recv(4096)


def upload(path: Path, key: str, content_type: str, cache: str = LONG_CACHE) -> None:
    internal().upload_file(
        str(path), settings.s3_public_bucket, key, ExtraArgs={"ContentType": content_type, "CacheControl": cache}
    )


def process_image(path: Path, work: Path, asset_id: str) -> dict[str, Any]:
    try:
        with Image.open(path) as source:
            source.seek(0)
            image = ImageOps.exif_transpose(source)
            image = image.convert("RGBA" if image.mode in {"RGBA", "LA", "P"} else "RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise Rejected("That image could not be read") from exc
    width, height = image.size
    colour = image.convert("RGB").resize((1, 1)).getpixel((0, 0))
    variants = []
    # Saving without exif= or icc metadata strips GPS and every other tag.
    targets = [w for w in WIDTHS if w < width] + [min(width, WIDTHS[-1])]
    for target in sorted(set(targets)):
        ratio = target / width
        resized = image if target == width else image.resize((target, max(1, round(height * ratio))), Image.Resampling.LANCZOS)
        webp, avif = work / f"{target}.webp", work / f"{target}.avif"
        resized.save(webp, "WEBP", quality=80, method=4)
        resized.save(avif, "AVIF", quality=60, speed=8)
        upload(webp, f"{asset_id}/{target}.webp", "image/webp")
        upload(avif, f"{asset_id}/{target}.avif", "image/avif")
        variants.append({"w": target, "webp": f"{asset_id}/{target}.webp", "avif": f"{asset_id}/{target}.avif"})
    return {
        "width": width, "height": height, "duration": None,
        "placeholder": _hex(colour),
        "variants": {"images": variants},
    }


def _hex(colour: Any) -> str:
    return "#{:02x}{:02x}{:02x}".format(*colour)


def _run(cmd: list[str], timeout: int = 1800) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)  # noqa: S603


def probe(path: Path) -> dict[str, Any]:
    res = _run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)], 120)
    if res.returncode != 0:
        raise Rejected("That video could not be read")
    data: dict[str, Any] = json.loads(res.stdout)
    return data


def process_audio(path: Path, work: Path, asset_id: str) -> dict[str, Any]:
    """Voice notes become AAC, which every browser plays. Re-encoding also drops metadata."""
    streams = probe(path).get("streams", [])
    if any(x.get("codec_type") == "video" for x in streams) or not any(x.get("codec_type") == "audio" for x in streams):
        raise Rejected("That file is not a voice note")
    out = work / "voice.m4a"
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-i", str(path), "-map", "0:a:0", "-map_metadata", "-1", "-c:a", "aac", "-b:a", "64k",
        "-t", str(settings.max_voice_seconds + 1), "-movflags", "+faststart", str(out),
    ]
    if _run(cmd, 300).returncode != 0:
        raise Rejected("That voice note could not be read")
    duration = float(probe(out).get("format", {}).get("duration") or 0)  # recordings from browsers often have none
    if duration > settings.max_voice_seconds:
        raise Rejected(f"That voice note is too long. The limit is {settings.max_voice_seconds} seconds.")
    key = f"{asset_id}/voice.m4a"
    upload(out, key, "audio/mp4")
    return {"width": None, "height": None, "duration": duration, "placeholder": None, "variants": {"audio": key}}


def process_video(path: Path, work: Path, asset_id: str, purpose: str) -> dict[str, Any]:
    info = probe(path)
    video = next((x for x in info.get("streams", []) if x.get("codec_type") == "video"), None)
    if video is None:
        raise Rejected("That file has no video track")
    duration = float(info.get("format", {}).get("duration") or video.get("duration") or 0)
    limit = getattr(settings, PURPOSE_SECONDS.get(purpose, "max_post_video_seconds"))
    if duration > limit:
        raise Rejected(f"That video is too long. The limit is {limit} seconds.")
    width, height = int(video["width"]), int(video["height"])
    rotation = abs(int(next(
        (s.get("rotation", 0) for s in video.get("side_data_list", []) if "rotation" in s),
        video.get("tags", {}).get("rotate", 0),
    )))
    if rotation in {90, 270}:
        width, height = height, width
    has_audio = any(x.get("codec_type") == "audio" for x in info.get("streams", []))
    short_side = min(width, height)
    rungs = [r for r in LADDER if r[0] <= short_side] or [LADDER[0]]
    master = ["#EXTM3U", "#EXT-X-VERSION:3"]
    for rung, v_rate, a_rate in rungs:
        rung_dir = work / f"{rung}p"
        rung_dir.mkdir()
        scale = f"scale=-2:{rung}" if height <= width else f"scale={rung}:-2"
        cmd = [
            "ffmpeg", "-y", "-v", "error", "-i", str(path), "-map", "0:v:0", "-map", "0:a:0?", "-map_metadata", "-1",
            "-vf", scale, "-c:v", "libx264", "-preset", "veryfast", "-profile:v", "main", "-pix_fmt", "yuv420p",
            "-b:v", v_rate, "-maxrate", v_rate, "-bufsize", v_rate, "-g", "48", "-sc_threshold", "0",
        ]
        cmd += ["-c:a", "aac", "-b:a", a_rate, "-ac", "2"] if has_audio else []
        cmd += ["-f", "hls", "-hls_time", "4", "-hls_playlist_type", "vod",
                "-hls_segment_filename", str(rung_dir / "s%04d.ts"), str(rung_dir / "index.m3u8")]
        res = _run(cmd)
        if res.returncode != 0:
            log.error("ffmpeg_failed", rung=rung, stderr=res.stderr[-500:].decode(errors="replace"))
            raise Rejected("That video could not be converted")
        for file in rung_dir.iterdir():
            is_list = file.suffix == ".m3u8"
            upload(file, f"{asset_id}/{rung}p/{file.name}",
                   "application/vnd.apple.mpegurl" if is_list else "video/mp2t", LONG_CACHE)
        bandwidth = int(v_rate[:-1]) * 1000 + int(a_rate[:-1]) * 1000
        res_w = round(width * rung / height) if height <= width else rung
        res_h = rung if height <= width else round(height * rung / width)
        master += [f"#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},RESOLUTION={res_w}x{res_h}", f"{rung}p/index.m3u8"]
    master_path = work / "master.m3u8"
    master_path.write_text("\n".join(master) + "\n")
    upload(master_path, f"{asset_id}/master.m3u8", "application/vnd.apple.mpegurl")

    frame = work / "poster.png"
    at = str(min(1.0, duration / 2))
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", at, "-i", str(path), "-frames:v", "1", "-map_metadata", "-1", str(frame)]
    res = _run(cmd, 120)
    if res.returncode != 0 or not frame.exists():
        raise Rejected("That video could not be converted")
    with Image.open(frame) as poster:
        rgb = poster.convert("RGB")
        colour = rgb.resize((1, 1)).getpixel((0, 0))
        rgb.thumbnail((1080, 1920))
        poster_path = work / "poster.webp"
        rgb.save(poster_path, "WEBP", quality=78)
    upload(poster_path, f"{asset_id}/poster.webp", "image/webp")
    return {
        "width": width, "height": height, "duration": duration,
        "placeholder": _hex(colour),
        "variants": {"hls": f"{asset_id}/master.m3u8", "poster": f"{asset_id}/poster.webp", "images": []},
    }


async def process_asset(asset_id: uuid.UUID) -> bool:
    """Idempotent. Returns True when the asset is ready to use."""
    async with SessionLocal() as s:
        asset = await repo.get(s, asset_id)
        if asset is None:
            return False
        if asset.status != "pending":
            return asset.status == "ready"
        work = Path(tempfile.mkdtemp(prefix="rsv-"))
        try:
            await _process(s, asset, work)
            asset.status = "ready"
        except Rejected as exc:
            asset.status, asset.error = "failed", str(exc)[:200]
        except ClientError:
            asset.status, asset.error = "failed", "The upload never arrived"
        finally:
            shutil.rmtree(work, ignore_errors=True)
        await s.commit()
        return asset.status == "ready"


async def _process(s: Any, asset: MediaAsset, work: Path) -> None:
    raw = work / "raw"
    store = internal()
    store.download_file(settings.s3_raw_bucket, asset.raw_key, str(raw))
    size = raw.stat().st_size
    limit = {"image": settings.max_image_bytes, "audio": settings.max_audio_bytes}.get(asset.kind, settings.max_video_bytes)
    if size > limit or size != asset.size_bytes:
        raise Rejected("The file size does not match the upload")
    with raw.open("rb") as handle:
        head = handle.read(32)
    if not (audio_container_ok(head) if asset.kind == "audio" else sniff(head) == asset.kind):
        raise Rejected("The file content does not match its type")
    digest = hashlib.sha256()
    with raw.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    asset.sha256 = digest.hexdigest()
    if await repo.is_blocked_hash(s, asset.sha256):
        asset.status = "blocked"
        log.warning("blocked_hash_upload", asset_id=str(asset.id), owner=str(asset.owner_id))
        raise Rejected("This file cannot be uploaded")
    if not clamav_clean(raw):
        raise Rejected("This file failed a security scan")
    if asset.kind == "image":
        result = process_image(raw, work, str(asset.id))
    elif asset.kind == "audio":
        result = process_audio(raw, work, str(asset.id))
    else:
        result = process_video(raw, work, str(asset.id), asset.purpose)
    asset.width, asset.height, asset.duration = result["width"], result["height"], result["duration"]
    asset.placeholder, asset.variants = result["placeholder"], result["variants"]
    if not (asset.kind == "video" and settings.whisper_enabled):  # subtitles still need the original
        store.delete_object(Bucket=settings.s3_raw_bucket, Key=asset.raw_key)


@celery.task(name="media.process_asset", time_limit=3600)
def process_asset_task(asset_id: str) -> None:
    if run(process_asset(uuid.UUID(asset_id))) and captions_enabled():
        run(enqueue("ai.suggest_captions", asset_id, queue="ai"))


async def _process_post(post_id: uuid.UUID) -> None:
    async with SessionLocal() as s:
        post = await post_repo.get(s, post_id)
        if post is None or post.status != "processing":
            return
        asset_ids = [m.asset_id for m in post.media]
        author_id = post.author_id
    results = [await process_asset(a) for a in asset_ids]
    if all(results):
        await enqueue("ai.enrich_post", post_id, queue="ai")
        return
    async with SessionLocal() as s:
        post = await post_repo.get(s, post_id)
        if post:
            post.status = "failed"
            await s.commit()
        await posts.invalidate(post_id)
        await notify(s, author_id, "post_failed", None, post_id)


@celery.task(name="media.process_post", time_limit=7200)
def process_post(post_id: str) -> None:
    run(_process_post(uuid.UUID(post_id)))
