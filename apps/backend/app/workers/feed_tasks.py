"""Scheduled upkeep: counters, scheduled posts, expiry, account purge, partitions."""
import uuid
from datetime import date

import structlog
from sqlalchemy import text

from app import models  # noqa: F401
from app.core.cache import counter_drain
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.events import enqueue
from app.core.storage import internal
from app.modules.posts import repository as post_repo
from app.modules.posts import service as posts
from app.modules.stories import repository as stories
from app.modules.users import repository as users
from app.workers.celery_app import celery
from app.workers.runtime import run

log = structlog.get_logger()
PARTITIONED = ("messages", "notifications")


async def _flush() -> int:
    drained = await counter_drain()
    if not drained:
        return 0
    async with SessionLocal() as s:
        for post_id, deltas in drained.items():
            await post_repo.apply_counters(s, post_id, deltas)
        await s.commit()
    for post_id in drained:
        await posts.invalidate(post_id)
    return len(drained)


@celery.task(name="feed.flush_counters")
def flush_counters() -> None:
    run(_flush())


async def _publish_scheduled() -> None:
    async with SessionLocal() as s:
        due = await post_repo.due_scheduled(s)
        for post_id in due:
            post = await post_repo.get(s, post_id)
            if post:
                post.status = "processing"
        await s.commit()
    for post_id in due:
        await posts.invalidate(post_id)
        await enqueue("media.process_post", post_id, queue="media")


@celery.task(name="feed.publish_scheduled")
def publish_scheduled() -> None:
    run(_publish_scheduled())


async def _purge_stories() -> None:
    async with SessionLocal() as s:
        count = await stories.purge_expired(s)
        await s.commit()
    log.info("stories_purged", count=count)


@celery.task(name="feed.purge_stories")
def purge_stories() -> None:
    run(_purge_stories())


def delete_stored_media(owner_id: uuid.UUID, asset_ids: list[uuid.UUID]) -> None:
    store = internal()
    for asset_id in asset_ids:
        pages = store.get_paginator("list_objects_v2").paginate(Bucket=settings.s3_public_bucket, Prefix=f"{asset_id}/")
        for page in pages:
            for item in page.get("Contents", []):
                store.delete_object(Bucket=settings.s3_public_bucket, Key=item["Key"])
        store.delete_object(Bucket=settings.s3_raw_bucket, Key=f"{owner_id}/{asset_id}")


async def _purge_accounts() -> None:
    async with SessionLocal() as s:
        for user_id in await users.users_due_for_purge(s):
            result = await users.purge(s, user_id)
            await users.audit(s, None, "account.purged", str(user_id))
            await s.commit()
            delete_stored_media(user_id, result.asset_ids)
            for post_id in result.touched_post_ids:
                await posts.invalidate(post_id)


@celery.task(name="feed.purge_accounts")
def purge_accounts() -> None:
    run(_purge_accounts())


def month_ranges(start: date, months: int) -> list[tuple[date, date]]:
    result = []
    year, month = start.year, start.month
    for _ in range(months):
        ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
        result.append((date(year, month, 1), date(ny, nm, 1)))
        year, month = ny, nm
    return result


def partition_sql(table: str, a: date, b: date) -> str:
    if table not in PARTITIONED:
        raise ValueError(table)
    return (
        f"CREATE TABLE IF NOT EXISTS {table}_{a:%Y_%m} PARTITION OF {table} "  # noqa: S608 - fixed identifiers
        f"FOR VALUES FROM ('{a.isoformat()}') TO ('{b.isoformat()}')"
    )


async def _ensure_partitions() -> None:
    async with SessionLocal() as s:
        # Next month onward: the current month is covered by an earlier run or by the migration.
        for a, b in month_ranges(date.today(), 4)[1:]:
            for table in PARTITIONED:
                await s.execute(text(partition_sql(table, a, b)))
        await s.commit()


@celery.task(name="feed.ensure_partitions")
def ensure_partitions() -> None:
    run(_ensure_partitions())
