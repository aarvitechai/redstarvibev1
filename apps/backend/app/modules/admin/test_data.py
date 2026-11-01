"""Creates and removes tracked test data. Runs in a worker, because media processing takes time."""
import secrets
import subprocess  # noqa: S404
import tempfile
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings.provider import embed_query, model_name
from app.ai.models import Embedding
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.errors import AppError, conflict, forbidden, not_found
from app.core.events import enqueue
from app.core.ids import uuid7
from app.core.storage import internal
from app.modules.admin import repository as repo
from app.modules.admin.models import TestDataBatch
from app.modules.admin.test_art import THEMES, artwork, avatar
from app.modules.comments.models import Comment
from app.modules.feed.service import invalidate_feed
from app.modules.follows.models import Follow
from app.modules.media.models import MediaAsset
from app.modules.posts import repository as post_repo
from app.modules.posts import service as posts
from app.modules.posts.models import Like, Post, PostMedia
from app.modules.posts.service import extract_hashtags
from app.modules.stories.models import Story
from app.modules.users import repository as users
from app.modules.users.models import Profile, User

CAPTIONS = [
    "Golden hour never gets old #sunset #test",
    "Morning walk through the old lanes #street #test",
    "Green everywhere after the rain #nature #test",
    "Night drive with the windows down #roadtrip #test",
    "First snow of the season #mountains #test",
]
PLACES = ["Varkala", "Old Delhi", "Munnar", "Pune", "Spiti"]
COMMENTS = ["Love this!", "Where is this?", "So good", "Beautiful shot", "Need to go here"]
NAMES = ["Aarav", "Diya", "Vihaan", "Ananya", "Ishaan", "Kavya", "Reyansh", "Saanvi", "Arjun", "Myra"]


class BatchIn(BaseModel):
    label: str = Field("Test data", min_length=1, max_length=80)
    users: int = Field(10, ge=2, le=50)
    posts_per_user: int = Field(3, ge=0, le=10)
    reels: int = Field(2, ge=0, le=5)
    stories: int = Field(3, ge=0, le=20)


class BatchOut(BaseModel):
    id: uuid.UUID
    label: str
    status: str
    error: str | None
    user_count: int
    post_count: int
    created_at: datetime
    removed_at: datetime | None


def batch_out(b: TestDataBatch) -> BatchOut:
    return BatchOut(
        id=b.id, label=b.label, status=b.status, error=b.error, user_count=b.user_count, post_count=b.post_count,
        created_at=b.created_at, removed_at=b.removed_at,
    )


def _ensure_allowed() -> None:
    if settings.app_env == "production" and not settings.allow_test_data:
        raise forbidden("Test data is turned off here. Set ALLOW_TEST_DATA=true to allow it.")


async def request_create(s: AsyncSession, admin: User, data: BatchIn, ip: str | None) -> BatchOut:
    _ensure_allowed()
    batch = TestDataBatch(label=data.label.strip(), params=data.model_dump(exclude={"label"}), created_by=admin.id)
    await repo.add_batch(s, batch)
    await users.audit(s, admin.id, "admin.test_data.create", str(batch.id), ip, batch.params)
    await s.commit()
    await enqueue("admin.create_test_batch", batch.id, queue="media")
    return batch_out(batch)


async def _start_removal(s: AsyncSession, admin: User, batch: TestDataBatch, ip: str | None) -> None:
    batch.status = "removing"
    await users.audit(s, admin.id, "admin.test_data.remove", str(batch.id), ip)
    await s.commit()
    await enqueue("admin.remove_test_batch", batch.id, queue="media")


async def request_remove(s: AsyncSession, admin: User, batch_id: uuid.UUID, ip: str | None) -> BatchOut:
    batch = await repo.get_batch(s, batch_id)
    if batch is None:
        raise not_found("Batch")
    stuck = batch.status == "creating" and datetime.now(UTC) - batch.created_at > timedelta(hours=1)
    if batch.status not in {"ready", "failed"} and not stuck:
        raise conflict("batch_busy", f"This batch cannot be removed while it is {batch.status}")
    await _start_removal(s, admin, batch, ip)
    return batch_out(batch)


async def request_remove_all(s: AsyncSession, admin: User, ip: str | None) -> int:
    batches = await repo.removable_batches(s)
    for batch in batches:
        await _start_removal(s, admin, batch, ip)
    return len(batches)


# ---- worker side ----
def make_test_clip() -> bytes:
    """A 3 second vertical test pattern with a tone."""
    with tempfile.TemporaryDirectory(prefix="rsv-") as work:
        path = Path(work) / "reel.mp4"
        subprocess.run(  # noqa: S603
            ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=720x1280:rate=24:duration=3",  # noqa: S607
             "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-shortest", str(path)],
            check=True, capture_output=True, timeout=120,
        )
        return path.read_bytes()


async def store_and_process(
    s: AsyncSession, owner: uuid.UUID, purpose: str, data: bytes, kind: str = "image"
) -> MediaAsset:
    """Through the real media pipeline, so test data looks exactly like uploaded content."""
    from app.workers.media_tasks import process_asset

    asset_id = uuid7()
    content_type = "image/jpeg" if kind == "image" else "video/mp4"
    key = f"{owner}/{asset_id}"
    internal().put_object(Bucket=settings.s3_raw_bucket, Key=key, Body=data, ContentType=content_type)
    asset = MediaAsset(
        id=asset_id, owner_id=owner, purpose=purpose, kind=kind, raw_key=key, declared_type=content_type, size_bytes=len(data)
    )
    s.add(asset)
    await s.commit()
    await process_asset(asset_id)
    await s.refresh(asset)
    if asset.status != "ready":
        raise AppError(500, "media_failed", asset.error or "Test media could not be processed")
    return asset


async def _publish(s: AsyncSession, author: User, asset: MediaAsset, caption: str, place: str | None, reel: bool) -> Post:
    """Publishes directly: no moderation call to the paid Claude API and no notifications for fake content."""
    post = Post(author_id=author.id, caption=caption, location=place, status="published", is_reel=reel)
    post.media = [PostMedia(asset_id=asset.id, position=0)]
    s.add(post)
    await s.flush()
    await post_repo.link_hashtags(s, post.id, extract_hashtags(caption))
    await users.bump_counts(s, author.id, post_count=1)
    s.add(Embedding(
        entity_type="post", entity_id=str(post.id), owner_id=author.id, chunk=caption,
        model=model_name(), vector=await embed_query(caption),
    ))
    await s.commit()
    return post


async def _add_engagement(s: AsyncSession, people: list[User], post_rows: list[Post], seed: int) -> None:
    n = len(people)
    for i, person in enumerate(people):
        for step in range(1, min(4, n)):
            other = people[(i + step) % n]
            s.add(Follow(follower_id=person.id, followee_id=other.id, status="active"))
            await users.bump_counts(s, person.id, following_count=1)
            await users.bump_counts(s, other.id, follower_count=1)
    for i, post in enumerate(post_rows):
        fans = [p for p in people if p.id != post.author_id][: 1 + (i + seed) % max(1, n - 1)]
        for fan in fans:
            await s.execute(insert(Like).values(user_id=fan.id, post_id=post.id).on_conflict_do_nothing())
        commenters = fans[:2]
        for j, fan in enumerate(commenters):
            s.add(Comment(post_id=post.id, author_id=fan.id, body=COMMENTS[(i + j) % len(COMMENTS)]))
        post.like_count, post.comment_count = len(fans), len(commenters)
    await s.commit()


async def create_batch(batch_id: uuid.UUID) -> None:
    async with SessionLocal() as s:
        batch = await repo.get_batch(s, batch_id)
        if batch is None or batch.status != "creating":
            return
        p = batch.params
        try:
            people: list[User] = []
            for i in range(p["users"]):
                # No password and an undeliverable address (RFC 2606), so nobody can log in as a test account.
                username = f"test_{secrets.token_hex(4)}"
                user = User(
                    username=username, email=f"{username}@test-data.invalid", password_hash=None, status="active",
                    date_of_birth=date(1995, 1, 1), test_batch_id=batch.id,
                )
                name = f"{NAMES[i % len(NAMES)]} (test)"
                await users.add_user(s, user, Profile(display_name=name, bio="Test account. Not a real person."))
                batch.user_count = i + 1
                await s.commit()
                picture = await store_and_process(s, user.id, "avatar", avatar(i))
                user.profile.avatar_key = (picture.variants or {})["images"][-1]["webp"]
                await s.commit()
                people.append(user)
            rows: list[Post] = []
            themes = list(THEMES)
            for i, author in enumerate(people):
                for j in range(p["posts_per_user"]):
                    n = i * 7 + j
                    asset = await store_and_process(
                        s, author.id, "post", artwork(themes[n % len(themes)], n, (720, 900))
                    )
                    rows.append(await _publish(s, author, asset, CAPTIONS[n % len(CAPTIONS)], PLACES[n % len(PLACES)], False))
                    batch.post_count = len(rows)
                    await s.commit()
            if p["reels"]:
                clip = make_test_clip()
                for i in range(p["reels"]):
                    author = people[i % len(people)]
                    asset = await store_and_process(s, author.id, "reel", clip, "video")
                    rows.append(await _publish(s, author, asset, f"Test reel {i + 1} #reel #test", None, True))
                    batch.post_count = len(rows)
                    await s.commit()
            for i in range(p["stories"]):
                author = people[i % len(people)]
                asset = await store_and_process(s, author.id, "story", artwork(themes[i % len(themes)], 100 + i, (720, 1280)))
                s.add(Story(
                    author_id=author.id, asset_id=asset.id, media_key=asset.raw_key,
                    expires_at=datetime.now(UTC) + timedelta(hours=24),
                ))
                await s.commit()
            await _add_engagement(s, people, rows, 3)
            batch.status = "ready"
            await s.commit()
        except Exception as exc:
            await s.rollback()
            batch = await repo.get_batch(s, batch_id)
            if batch:
                batch.status, batch.error = "failed", str(exc)[:300]  # what exists stays removable
                await s.commit()
            raise


async def remove_batch(batch_id: uuid.UUID) -> None:
    from app.workers.feed_tasks import delete_stored_media

    async with SessionLocal() as s:
        batch = await repo.get_batch(s, batch_id)
        if batch is None or batch.status != "removing":
            return
        for user_id in await repo.batch_user_ids(s, batch_id):
            post_ids = await repo.post_ids_of(s, user_id)
            followers = await repo.follower_ids(s, user_id)
            await repo.delete_references(s, user_id, post_ids)
            result = await users.purge(s, user_id)
            await s.commit()
            delete_stored_media(user_id, result.asset_ids)
            for post_id in [*post_ids, *result.touched_post_ids]:
                await posts.invalidate(post_id)
            for follower in followers:  # real people who followed a test account rebuild their feed
                await invalidate_feed(follower)
        batch = await repo.get_batch(s, batch_id)
        if batch:
            batch.status, batch.removed_at = "removed", datetime.now(UTC)
            await s.commit()
