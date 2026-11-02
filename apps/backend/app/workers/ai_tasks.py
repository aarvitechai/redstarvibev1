"""AI worker: moderation, embeddings, indexing, subtitles. Then the post becomes published."""
import io
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import structlog
from PIL import Image
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models  # noqa: F401
from app.ai.embeddings.search import embed_many, is_enabled
from app.ai.rag.ingest import delete_entity, ingest_help_docs, upsert_entity
from app.ai.safety.moderation import moderate
from app.ai.speech.whisper import transcribe_to_vtt
from app.ai.writing import suggest_from_image
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.events import emit, enqueue
from app.core.storage import internal
from app.modules.assistant.suggestions import store_captions
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
BACKFILL_BATCH = 200
CAPTION_IMAGE_WIDTH = 480


def _thumbnails(post: Post) -> list[bytes]:
    store = internal()
    data = []
    for media in post.media[:4]:
        v = media.asset.variants or {}
        key = v.get("poster") or (v["images"][0]["webp"] if v.get("images") else None)
        if key:
            data.append(store.get_object(Bucket=settings.s3_public_bucket, Key=key)["Body"].read())
    return data


async def _index_assistant(s: AsyncSession, post: Post) -> None:
    text = " ".join(filter(None, [post.full_text, post.location]))
    await delete_entity(s, "own_post", str(post.id))
    if text:
        await upsert_entity(s, "own_post", str(post.id), post.author_id, "Your post", text)


async def index_posts(post_ids: list[uuid.UUID]) -> bool:
    """Keyword index always, vectors when a model is on. False means the model did not answer."""
    async with SessionLocal() as s:
        rows = await post_repo.get_many(s, post_ids)
        texts = {p.id: " ".join(filter(None, [p.full_text, p.location])) for p in rows}
        with_text = [i for i, text in texts.items() if text]
        vectors = await embed_many([texts[i] for i in with_text]) if with_text else None
        by_id = dict(zip(with_text, vectors, strict=True)) if vectors else {}
        worked = not (is_enabled() and with_text and not vectors)
        now = datetime.now(UTC)
        for post in rows:
            post.search_text = texts[post.id]
            post.search_tsv = func.to_tsvector("simple", texts[post.id])
            post.indexed_at = now
            if post.id in by_id:
                post.embedding, post.embedding_model = by_id[post.id], settings.embed_model
            elif is_enabled() and not texts[post.id]:
                post.embedding_model = settings.embed_model  # nothing to embed, so stop asking
        await s.commit()
    return worked


async def pending_ids(limit: int) -> list[uuid.UUID]:
    """Posts never indexed, or indexed without a vector from the current model."""
    needs: ColumnElement[bool] = Post.indexed_at.is_(None)
    if is_enabled():
        needs = or_(needs, Post.embedding_model.is_distinct_from(settings.embed_model))
    q = select(Post.id).where(Post.status == "published", Post.deleted_at.is_(None), needs).limit(limit)
    async with SessionLocal() as s:
        return list((await s.execute(q)).scalars())


async def _backfill() -> None:
    while ids := await pending_ids(BACKFILL_BATCH):
        if not await index_posts(ids):
            log.warning("search_backfill_stopped")  # the model is down, so the nightly run tries again
            return


async def _suggest_captions(asset_id: uuid.UUID) -> None:
    async with SessionLocal() as s:
        asset = await media_repo.get(s, asset_id)
        if asset is None or asset.status != "ready" or asset.purpose not in {"post", "reel"} or not asset.variants:
            return
        images = asset.variants.get("images") or []
        small = next((i for i in images if i["w"] >= CAPTION_IMAGE_WIDTH), images[-1] if images else None)
        key = asset.variants.get("poster") or (small and small["webp"])
        is_video = asset.kind == "video"
    if not key:
        return
    data = internal().get_object(Bucket=settings.s3_public_bucket, Key=key)["Body"].read()
    await store_captions(asset_id, await suggest_from_image(_as_jpeg(data), is_video))


def _as_jpeg(data: bytes) -> bytes:
    """Vision models do not all read WebP."""
    out = io.BytesIO()
    Image.open(io.BytesIO(data)).convert("RGB").save(out, "JPEG", quality=85)
    return out.getvalue()


@celery.task(name="ai.index_post", time_limit=600)
def index_post(post_id: str) -> None:
    run(index_posts([uuid.UUID(post_id)]))


@celery.task(name="ai.backfill_search", time_limit=21600)
def backfill_search() -> None:
    run(_backfill())


@celery.task(name="ai.suggest_captions", time_limit=600)
def suggest_captions(asset_id: str) -> None:
    run(_suggest_captions(uuid.UUID(asset_id)))


async def _enrich(post_id: uuid.UUID) -> None:
    async with SessionLocal() as s:
        post = await post_repo.get(s, post_id)
        if post is None or post.status != "processing":
            return
        thumbs = _thumbnails(post)
        verdict = await moderate(post.full_text, thumbs)
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
        await _index_assistant(s, post)
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
