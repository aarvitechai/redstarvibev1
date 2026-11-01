"""AI worker: moderation, embeddings, indexing, subtitles. Then the post becomes published."""
import tempfile
import uuid
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app import models  # noqa: F401
from app.ai.embeddings.provider import embed_query, model_name
from app.ai.models import Embedding
from app.ai.rag.ingest import delete_entity, ingest_help_docs, upsert_entity
from app.ai.safety.moderation import moderate
from app.ai.speech.whisper import transcribe_to_vtt
from app.ai.vision.clip import embed_image_sync
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.events import emit, enqueue
from app.core.storage import internal
from app.modules.media import repository as media_repo
from app.modules.moderation import repository as mod_repo
from app.modules.moderation.models import Report
from app.modules.notifications.service import notify
from app.modules.posts import repository as post_repo
from app.modules.posts import service as posts
from app.modules.posts.models import Post
from app.modules.posts.service import extract_hashtags
from app.modules.users import repository as users
from app.workers.celery_app import celery
from app.workers.media_tasks import upload
from app.workers.runtime import run

log = structlog.get_logger()


def _thumbnails(post: Post) -> list[bytes]:
    store = internal()
    data = []
    for media in post.media[:4]:
        v = media.asset.variants or {}
        key = v.get("poster") or (v["images"][0]["webp"] if v.get("images") else None)
        if key:
            data.append(store.get_object(Bucket=settings.s3_public_bucket, Key=key)["Body"].read())
    return data


async def _index(s: AsyncSession, post: Post, thumbs: list[bytes]) -> None:
    text = " ".join(filter(None, [post.caption, post.location]))
    await delete_entity(s, "post", str(post.id))
    await delete_entity(s, "post_image", str(post.id))
    if text:
        s.add(Embedding(
            entity_type="post", entity_id=str(post.id), owner_id=post.author_id, chunk=text[:2000],
            model=model_name(), vector=await embed_query(text),
        ))
        await upsert_entity(s, "own_post", str(post.id), post.author_id, "Your post", text)
    if settings.clip_enabled and thumbs:
        vector = embed_image_sync(thumbs[0])
        if vector:
            s.add(Embedding(
                entity_type="post_image", entity_id=str(post.id), owner_id=post.author_id,
                model="open_clip/ViT-B-32", vector=vector,
            ))


async def _enrich(post_id: uuid.UUID) -> None:
    async with SessionLocal() as s:
        post = await post_repo.get(s, post_id)
        if post is None or post.status != "processing":
            return
        thumbs = _thumbnails(post)
        verdict = await moderate(post.caption, thumbs)
        if verdict.score >= 0.5:
            await mod_repo.add(s, Report(
                entity_type="post", entity_id=post.id, reason=verdict.category[:40], source="ai", score=verdict.score,
            ))
            await mod_repo.log_ai(
                s, "moderation", post.id, post.author_id, verdict.source, verdict.category, {"score": verdict.score}
            )
        if verdict.blocked:
            post.status = "blocked"
            await s.commit()
            await posts.invalidate(post.id)
            await notify(s, post.author_id, "post_failed", None, post.id)
            return
        await _index(s, post, thumbs)
        post.status = "published"
        await post_repo.link_hashtags(s, post.id, extract_hashtags(post.caption))
        await users.bump_counts(s, post.author_id, post_count=1)
        await s.commit()
        await posts.invalidate(post.id)
        needs_subtitles = settings.whisper_enabled and [m.asset_id for m in post.media if m.asset.kind == "video"]
    await emit("post.published", post_id=post_id)
    for asset_id in needs_subtitles or []:
        await enqueue("ai.subtitles", post_id, asset_id, queue="ai")


@celery.task(name="ai.enrich_post", bind=True, max_retries=3, default_retry_delay=30, time_limit=900)
def enrich_post(self, post_id: str) -> None:  # type: ignore[no-untyped-def]
    try:
        run(_enrich(uuid.UUID(post_id)))
    except Exception as exc:
        log.exception("enrich_failed", post_id=post_id)
        raise self.retry(exc=exc) from exc


async def _subtitles(post_id: uuid.UUID, asset_id: uuid.UUID) -> None:
    async with SessionLocal() as s:
        asset = await media_repo.get(s, asset_id)
        if asset is None or not asset.variants:
            return
        store = internal()
        with tempfile.TemporaryDirectory(prefix="rsv-") as work:
            raw = Path(work) / "raw"
            store.download_file(settings.s3_raw_bucket, asset.raw_key, str(raw))
            vtt = transcribe_to_vtt(str(raw))
            if vtt:
                path = Path(work) / "subtitles.vtt"
                path.write_text(vtt, encoding="utf8")
                key = f"{asset.id}/subtitles.vtt"
                upload(path, key, "text/vtt")
                asset.variants = {**asset.variants, "vtt": key}
                await mod_repo.log_ai(s, "subtitles", asset.id, asset.owner_id, f"whisper/{settings.whisper_model}", vtt[:4000])
        store.delete_object(Bucket=settings.s3_raw_bucket, Key=asset.raw_key)
        await s.commit()
    await posts.invalidate(post_id)


@celery.task(name="ai.subtitles", time_limit=3600)
def subtitles(post_id: str, asset_id: str) -> None:
    run(_subtitles(uuid.UUID(post_id), uuid.UUID(asset_id)))


async def _ingest_help() -> None:
    async with SessionLocal() as s:
        await ingest_help_docs(s)


@celery.task(name="ai.ingest_help")
def ingest_help() -> None:
    run(_ingest_help())
