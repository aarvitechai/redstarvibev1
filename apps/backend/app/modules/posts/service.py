"""Posts: creation, visibility policy, hydration with cache aside, likes, saves."""
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import (
    cache_delete,
    cache_get_many,
    cache_set_many,
    counter_incr,
    counter_pending,
    get_redis,
)
from app.core.config import settings
from app.core.errors import AppError, bad_request, conflict, forbidden, not_found
from app.core.events import emit, enqueue
from app.core.pagination import Page, encode_cursor
from app.core.rate_limit import hit
from app.modules.follows import repository as follows
from app.modules.media import repository as media_repo
from app.modules.media.service import asset_out
from app.modules.posts import repository as repo
from app.modules.posts.models import Collection, Post, PostCollab, PostMedia, PostTag
from app.modules.posts.schemas import (
    BestTimes,
    CapsuleTeaser,
    CollectionOut,
    HourStat,
    Insights,
    LikeResult,
    PostCreate,
    PostOut,
    PostUpdate,
    ScheduleRequest,
    ViewResult,
)
from app.modules.users import repository as users
from app.modules.users import service as user_service
from app.modules.users.models import User
from app.modules.users.schemas import DataExport
from app.realtime.pubsub import publish

HASHTAG_RE = re.compile(r"(?:^|\s)#(\w{1,60})", re.UNICODE)
MAX_PINS = 3
VIEW_WINDOW = 86400
BEST_TIME_DAYS = 90
BEST_TIME_MIN_LIKES = 20
SCHEDULE_REQUEST_SECONDS = 7 * 86400
VIEW_IP_LIMIT = 300  # visitor view requests per minute from one IP, high enough for a shared network
MENTION_RE = re.compile(r"(?:^|\s)@([a-zA-Z0-9_.]{3,30})")


def extract_hashtags(caption: str) -> list[str]:
    return sorted({t.lower() for t in HASHTAG_RE.findall(caption)})[:30]


def extract_mentions(caption: str) -> list[str]:
    return sorted({m.lower() for m in MENTION_RE.findall(caption)})[:20]


def _key(post_id: uuid.UUID) -> str:
    return f"post:{post_id}"


def _base(post: Post) -> dict[str, Any]:
    return PostOut(
        id=post.id, author=user_service.brief(post.author), caption=post.caption, location=post.location,
        visibility=post.visibility, status=post.status, is_reel=post.is_reel,
        media=[asset_out(m.asset, m.alt_text, m.text_overlay, m.edit) for m in post.media],
        tagged=[user_service.brief(u) for u in post.tagged],
        collaborator=user_service.brief(post.collab.user) if post.collab and post.collab.status == "accepted" else None,
        pinned=post.pinned_at is not None, is_capsule=post.is_capsule, music=post.music,
        like_count=post.like_count, comment_count=post.comment_count, view_count=post.view_count,
        save_count=post.save_count, created_at=post.created_at, scheduled_at=post.scheduled_at,
    ).model_dump(mode="json")


async def invalidate(post_id: uuid.UUID) -> None:
    await cache_delete(_key(post_id))


async def hydrate(s: AsyncSession, viewer: User | None, ids: list[uuid.UUID]) -> list[PostOut]:
    """Bulk load: Redis first, then Postgres. Counters add the deltas not flushed yet."""
    if not ids:
        return []
    cached = await cache_get_many([_key(i) for i in ids])
    data: dict[uuid.UUID, dict[str, Any]] = {i: c for i, c in zip(ids, cached, strict=True) if c}
    missing = [i for i in ids if i not in data]
    if missing:
        fresh = {p.id: _base(p) for p in await repo.get_many(s, missing) if p.deleted_at is None}
        data.update(fresh)
        await cache_set_many({_key(k): v for k, v in fresh.items()}, settings.object_cache_seconds)
    present = [i for i in ids if i in data]
    pending = await counter_pending(present)
    liked, saved = set(), set()
    if viewer:
        liked = await repo.liked_among(s, viewer.id, present)
        saved = await repo.saved_among(s, viewer.id, present)
    result = []
    for pid in present:
        out = PostOut(**data[pid])
        for field, delta in pending.get(pid, {}).items():
            setattr(out, field, max(0, getattr(out, field) + delta))
        out.liked, out.saved = pid in liked, pid in saved
        out.is_own = bool(viewer and out.author.id == viewer.id)
        result.append(out)
    return result


async def can_view(s: AsyncSession, viewer: User | None, post: Post) -> bool:
    is_owner = bool(viewer and viewer.id == post.author_id)
    if post.status != "published":
        return is_owner
    if is_owner:
        return True
    if not await user_service.can_view_content_of(s, viewer, post.author):
        return False
    if post.visibility == "followers":
        return bool(viewer and await follows.status_of(s, viewer.id, post.author_id) == "active")
    return True


async def get_viewable(s: AsyncSession, viewer: User | None, post_id: uuid.UUID) -> Post:
    post = await repo.get(s, post_id)
    if post is None or not await can_view(s, viewer, post):
        raise not_found("Post")  # 404, not 403: do not reveal that a private post exists
    return post


async def get_post(s: AsyncSession, viewer: User | None, post_id: uuid.UUID) -> PostOut:
    await get_viewable(s, viewer, post_id)
    return (await hydrate(s, viewer, [post_id]))[0]


async def _add_tags(s: AsyncSession, author: User, post_id: uuid.UUID, usernames: list[str]) -> None:
    wanted = {u.strip().lstrip("@").lower() for u in usernames if u.strip()}
    people = await users.by_usernames(s, list(wanted))
    allowed = [
        u for u in people
        if u.status == "active" and not await users.is_blocked_either_way(s, author.id, u.id)
    ]
    if len(allowed) != len(wanted):  # one message for every reason, so this cannot be used to discover blocks
        raise bad_request("invalid_tag", "One of those people cannot be tagged")
    for person in allowed:
        s.add(PostTag(post_id=post_id, user_id=person.id))
    await s.flush()


async def _invite_collab(s: AsyncSession, author: User, post_id: uuid.UUID, username: str) -> None:
    person = await users.by_username(s, username.strip().lstrip("@"))
    if (
        person is None or person.id == author.id or person.status != "active"
        or await users.is_blocked_either_way(s, author.id, person.id)
    ):
        raise bad_request("invalid_collab", "That person cannot be invited")
    s.add(PostCollab(post_id=post_id, user_id=person.id))
    await s.flush()


async def collab_requests(s: AsyncSession, user: User) -> list[PostOut]:
    return await hydrate(s, user, await repo.pending_collab_post_ids(s, user.id))


async def accept_collab(s: AsyncSession, user: User, post_id: uuid.UUID) -> None:
    if not await repo.set_collab_accepted(s, post_id, user.id):
        raise not_found("Invite")
    await s.commit()
    await invalidate(post_id)
    await emit("post.collab_accepted", post_id=post_id, user_id=user.id)


async def remove_collab(s: AsyncSession, user: User, post_id: uuid.UUID) -> None:
    """Declines an invite, or leaves a post. Either way the person's name comes off it."""
    if not await repo.remove_collab(s, post_id, user.id):
        raise not_found("Invite")
    await s.commit()
    await invalidate(post_id)


async def pin(s: AsyncSession, user: User, post_id: uuid.UUID) -> None:
    post = await _owned(s, user, post_id)
    if post.status != "published":
        raise bad_request("not_published", "Only published posts can be pinned")
    if post.pinned_at is None:
        if await repo.pinned_count(s, user.id) >= MAX_PINS:
            raise conflict("too_many_pins", f"You can pin up to {MAX_PINS} posts. Unpin one first.")
        post.pinned_at = datetime.now(UTC)
    await s.commit()
    await invalidate(post_id)


async def unpin(s: AsyncSession, user: User, post_id: uuid.UUID) -> None:
    post = await _owned(s, user, post_id)
    post.pinned_at = None
    await s.commit()
    await invalidate(post_id)


async def capsule_teaser(s: AsyncSession, viewer: User | None, username: str) -> CapsuleTeaser:
    """How many are sealed and when the next one opens. Nothing about what is inside."""
    author = await user_service.get_visible_user(s, viewer, username)
    if not await user_service.can_view_content_of(s, viewer, author):
        return CapsuleTeaser(count=0, next_unlock_at=None)
    count, next_at = await repo.capsule_summary(s, author.id)
    return CapsuleTeaser(count=count, next_unlock_at=next_at)


async def remove_my_tag(s: AsyncSession, user: User, post_id: uuid.UUID) -> None:
    if not await repo.remove_tag(s, post_id, user.id):
        raise not_found("Tag")
    await s.commit()
    await invalidate(post_id)


async def create_post(s: AsyncSession, user: User, data: PostCreate, idempotency_key: str | None) -> PostOut:
    await hit(f"post:user:{user.id}", 30, 3600)
    idem = f"idem:post:{user.id}:{idempotency_key}" if idempotency_key else None
    if idem:
        client = get_redis()
        if not await client.set(idem, "pending", nx=True, ex=86400):
            existing = await client.get(idem)
            if existing and existing != "pending":
                return (await hydrate(s, user, [uuid.UUID(str(existing))]))[0]
            raise conflict("duplicate_request", "This post is already being created")
    try:
        assets = await media_repo.get_owned(s, data.asset_ids, user.id)
        if len(assets) != len(set(data.asset_ids)):
            raise bad_request("invalid_media", "One of those uploads does not exist")
        if any(a.status in {"failed", "blocked"} or a.purpose not in {"post", "reel"} for a in assets):
            raise bad_request("invalid_media", "One of those uploads cannot be used")
        if data.is_reel and (len(assets) != 1 or assets[0].kind != "video"):
            raise bad_request("reel_needs_video", "A reel must be exactly one video")
        status = "processing"
        if data.is_capsule and (data.draft or not data.scheduled_at):
            raise bad_request("capsule_needs_date", "A time capsule needs a date to open")
        if data.scheduled_at:
            if data.scheduled_at <= datetime.now(UTC):
                raise bad_request("invalid_schedule", "Schedule time must be in the future")
            status = "scheduled"
        if data.draft:
            status = "draft"
        alts = data.alt_texts or []
        overlays = data.text_overlays or []
        edits = data.media_edits or []
        post = Post(
            author_id=user.id, caption=data.caption.strip(), location=(data.location or "").strip() or None,
            visibility=data.visibility, is_reel=data.is_reel, status=status, scheduled_at=data.scheduled_at,
            is_capsule=data.is_capsule, music=data.music,
        )
        post.media = [
            PostMedia(
                asset_id=aid, position=i, alt_text=(alts[i] if i < len(alts) else None),
                text_overlay=(overlay.model_dump() if i < len(overlays) and (overlay := overlays[i]) else None),
                edit=(edit.model_dump() if i < len(edits) and (edit := edits[i]) else None),
            )
            for i, aid in enumerate(data.asset_ids)
        ]
        await repo.add(s, post)
        await _add_tags(s, user, post.id, data.tagged_usernames)
        if data.collab_username:
            await _invite_collab(s, user, post.id, data.collab_username)
        await s.commit()
    except Exception:
        if idem:
            await get_redis().delete(idem)
        raise
    if idem:
        await get_redis().set(idem, str(post.id), ex=86400)
    if status == "processing":
        await enqueue("media.process_post", post.id, queue="media")
    return (await hydrate(s, user, [post.id]))[0]


async def _owned(s: AsyncSession, user: User, post_id: uuid.UUID) -> Post:
    post = await repo.get(s, post_id)
    if post is None:
        raise not_found("Post")
    if post.author_id != user.id:
        raise forbidden("This is not your post")
    return post


async def update_post(s: AsyncSession, user: User, post_id: uuid.UUID, data: PostUpdate) -> PostOut:
    post = await _owned(s, user, post_id)
    if data.caption is not None:
        post.caption = data.caption.strip()
        if post.status == "published":
            await repo.unlink_hashtags(s, post.id)
            await repo.link_hashtags(s, post.id, extract_hashtags(post.caption))
    if "location" in data.model_fields_set:
        post.location = (data.location or "").strip() or None
    if data.visibility:
        post.visibility = data.visibility
    await s.commit()
    await invalidate(post.id)
    if post.status == "published":
        await emit("post.updated", post_id=post.id)
    return (await hydrate(s, user, [post.id]))[0]


async def delete_post(s: AsyncSession, user: User, post_id: uuid.UUID) -> None:
    post = await _owned(s, user, post_id)
    was_published = post.status == "published"
    post.deleted_at = datetime.now(UTC)
    if was_published:
        await users.bump_counts(s, user.id, post_count=-1)
        await repo.unlink_hashtags(s, post.id)
    await s.commit()
    await invalidate(post.id)
    await emit("post.deleted", post_id=post.id, author_id=user.id)


async def publish_draft(s: AsyncSession, user: User, post_id: uuid.UUID) -> PostOut:
    post = await _owned(s, user, post_id)
    if post.status not in {"draft", "scheduled"}:
        raise conflict("not_draft", "Only drafts can be published")
    if post.is_capsule:
        raise conflict("capsule_sealed", "A time capsule opens on its date")
    post.status, post.scheduled_at = "processing", None
    await s.commit()
    await invalidate(post.id)
    await enqueue("media.process_post", post.id, queue="media")
    return (await hydrate(s, user, [post.id]))[0]


async def best_times(s: AsyncSession, user: User, tz: str) -> BestTimes:
    """Plain statistics on when other people like this person's posts. No model involved."""
    if not await repo.is_timezone(s, tz):
        raise bad_request("invalid_timezone", "Unknown time zone")
    rows = await repo.likes_by_hour(s, user.id, tz, BEST_TIME_DAYS)
    top = sorted(rows, key=lambda r: (-r[1], r[0]))[:3]
    return BestTimes(
        enough_data=sum(n for _, n in rows) >= BEST_TIME_MIN_LIKES,
        hours=[HourStat(hour=h, likes=n) for h, n in top],
    )


def _schedule_key(user_id: uuid.UUID) -> str:
    return f"mcp:schedule:{user_id}"


async def request_schedule(s: AsyncSession, user: User, post_id: uuid.UUID, when: datetime) -> None:
    """An AI client can only ask. The person approves in the app, which an MCP token cannot reach."""
    post = await _owned(s, user, post_id)
    if post.status != "draft":
        raise conflict("not_draft", "Only drafts can be scheduled")
    if when.tzinfo is None or when <= datetime.now(UTC):
        raise bad_request("invalid_schedule", "Schedule time must be in the future, with a time zone")
    client = get_redis()
    await client.hset(_schedule_key(user.id), str(post_id), when.isoformat())
    await client.expire(_schedule_key(user.id), SCHEDULE_REQUEST_SECONDS)


async def schedule_requests(s: AsyncSession, user: User) -> list[ScheduleRequest]:
    stored = {str(k): str(v) for k, v in (await get_redis().hgetall(_schedule_key(user.id))).items()}
    drafts = {
        p.id: p for p in await hydrate(s, user, [uuid.UUID(i) for i in stored]) if p.is_own and p.status == "draft"
    }
    return [
        ScheduleRequest(post_id=i, caption=p.caption, publish_at=datetime.fromisoformat(stored[str(i)]))
        for i, p in drafts.items()
    ]


async def approve_schedule(s: AsyncSession, user: User, post_id: uuid.UUID) -> PostOut:
    stored = await get_redis().hget(_schedule_key(user.id), str(post_id))
    if stored is None:
        raise not_found("Request")
    out = await schedule_draft(s, user, post_id, datetime.fromisoformat(str(stored)))
    await get_redis().hdel(_schedule_key(user.id), str(post_id))
    return out


async def decline_schedule(user: User, post_id: uuid.UUID) -> None:
    await get_redis().hdel(_schedule_key(user.id), str(post_id))


async def schedule_draft(s: AsyncSession, user: User, post_id: uuid.UUID, when: datetime) -> PostOut:
    post = await _owned(s, user, post_id)
    if post.status != "draft":
        raise conflict("not_draft", "Only drafts can be scheduled")
    if when <= datetime.now(UTC):
        raise bad_request("invalid_schedule", "Schedule time must be in the future")
    post.status, post.scheduled_at = "scheduled", when
    await s.commit()
    await invalidate(post.id)
    return (await hydrate(s, user, [post.id]))[0]


async def _publish_count(post_id: uuid.UUID, field: str, count: int) -> None:
    await publish(f"post:{post_id}", {"type": "counter", "post_id": str(post_id), "field": field, "value": count})


async def like(s: AsyncSession, user: User, post_id: uuid.UUID) -> LikeResult:
    await hit(f"like:user:{user.id}", 300, 3600)
    post = await get_viewable(s, user, post_id)
    created = await repo.like(s, user.id, post.id)
    await s.commit()
    if created:
        await counter_incr(post.id, "like_count", 1)
        await emit("post.liked", post_id=post.id, actor_id=user.id, author_id=post.author_id)
    out = (await hydrate(s, user, [post.id]))[0]
    await _publish_count(post.id, "like_count", out.like_count)
    return LikeResult(liked=True, like_count=out.like_count)


async def unlike(s: AsyncSession, user: User, post_id: uuid.UUID) -> LikeResult:
    post = await get_viewable(s, user, post_id)
    removed = await repo.unlike(s, user.id, post.id)
    await s.commit()
    if removed:
        await counter_incr(post.id, "like_count", -1)
    out = (await hydrate(s, user, [post.id]))[0]
    await _publish_count(post.id, "like_count", out.like_count)
    return LikeResult(liked=False, like_count=out.like_count)


async def save(s: AsyncSession, user: User, post_id: uuid.UUID, collection_id: uuid.UUID | None) -> None:
    post = await get_viewable(s, user, post_id)
    if collection_id:
        coll = await repo.collection(s, collection_id)
        if coll is None or coll.user_id != user.id:
            raise not_found("Collection")
    if await repo.save(s, user.id, post.id, collection_id):
        await counter_incr(post.id, "save_count", 1)
    await s.commit()


async def unsave(s: AsyncSession, user: User, post_id: uuid.UUID) -> None:
    if await repo.unsave(s, user.id, post_id):
        await counter_incr(post_id, "save_count", -1)
    await s.commit()


async def record_view(
    s: AsyncSession, viewer: User | None, post_id: uuid.UUID, visitor_id: str | None, ip: str
) -> tuple[ViewResult, str | None]:
    """One view per person per post per day. Returns the visitor id to store when a new cookie is needed.

    Logged in people are counted by account, so clearing cookies cannot add views. Visitors are counted by
    cookie, and a limit per IP stops a script that sends a new cookie every time.
    """
    post = await get_viewable(s, viewer, post_id)
    new_visitor = None
    if viewer:
        who = f"u:{viewer.id}"
    else:
        if not visitor_id:
            visitor_id = new_visitor = uuid.uuid4().hex
        who = f"c:{visitor_id}"
    counted = False
    if post.status == "published" and post.author_id != (viewer.id if viewer else None):
        try:
            if not viewer:
                await hit(f"view:ip:{ip}", VIEW_IP_LIMIT, 60)
            counted = bool(await get_redis().set(f"viewed:{post_id}:{who}", "1", nx=True, ex=VIEW_WINDOW))
        except AppError:
            counted = False  # over the limit: show the page normally, just do not count it
    if counted:
        await counter_incr(post_id, "view_count", 1)
    out = (await hydrate(s, viewer, [post_id]))[0]
    if counted:
        await _publish_count(post_id, "view_count", out.view_count)
    return ViewResult(view_count=out.view_count, counted=counted), new_visitor


async def saved_page(
    s: AsyncSession, user: User, collection_id: uuid.UUID | None, cursor: uuid.UUID | None, limit: int
) -> Page[PostOut]:
    if collection_id:
        coll = await repo.collection(s, collection_id)
        if coll is None or coll.user_id != user.id:
            raise not_found("Collection")
    rows = await repo.saved_ids(s, user.id, collection_id, cursor, limit + 1)
    more = len(rows) > limit
    rows = rows[:limit]
    items = await hydrate(s, user, [pid for _, pid in rows])
    return Page(items=items, next_cursor=encode_cursor(rows[-1][0]) if more else None)


async def create_collection(s: AsyncSession, user: User, name: str) -> CollectionOut:
    coll = Collection(user_id=user.id, name=name.strip())
    await repo.add_collection(s, coll)
    await s.commit()
    return CollectionOut(id=coll.id, name=coll.name)


async def delete_collection(s: AsyncSession, user: User, collection_id: uuid.UUID) -> None:
    coll = await repo.collection(s, collection_id)
    if coll is None or coll.user_id != user.id:
        raise not_found("Collection")
    await repo.remove_collection(s, collection_id)
    await s.commit()


async def insights(s: AsyncSession, user: User, post_id: uuid.UUID) -> Insights:
    await _owned(s, user, post_id)
    out = (await hydrate(s, user, [post_id]))[0]
    denom = max(out.view_count, user.follower_count, 1)
    rate = (out.like_count + out.comment_count + out.save_count) / denom
    return Insights(
        post_id=post_id, views=out.view_count, likes=out.like_count, comments=out.comment_count,
        saves=out.save_count, engagement_rate=round(rate, 4),
    )


async def export_user_data(s: AsyncSession, user: User) -> DataExport:
    """Data portability (DPDP Act 2023, GDPR article 20)."""
    posts = await repo.export_posts(s, user.id)
    comments = await repo.export_comments(s, user.id)
    following = await users.by_ids(s, await follows.active_followee_ids(s, user.id))
    followers = await users.by_ids(s, await follows.active_follower_ids(s, user.id))
    return DataExport(
        profile={
            "username": user.username, "email": user.email, "display_name": user.profile.display_name,
            "bio": user.profile.bio, "website": user.profile.website, "is_private": user.is_private,
            "date_of_birth": str(user.date_of_birth) if user.date_of_birth else None,
            "created_at": user.created_at.isoformat(),
            "interests": await users.interests_of(s, user.id),
        },
        posts=[
            {"id": str(p.id), "caption": p.caption, "text_on_media": p.overlay_texts, "location": p.location,
             "status": p.status, "created_at": p.created_at.isoformat()} for p in posts
        ],
        comments=[
            {"id": str(c.id), "post_id": str(c.post_id), "body": c.body, "created_at": c.created_at.isoformat()}
            for c in comments
        ],
        following=[u.username for u in following.values()],
        followers=[u.username for u in followers.values()],
        saved_post_ids=[str(i) for i in await repo.export_saved(s, user.id)],
    )
