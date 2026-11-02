"""Numbers for the admin and super admin dashboards. People and content counts leave out generated test accounts."""
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.cache import get_redis
from app.core.pagination import Page, encode_cursor
from app.modules.admin.models import TestDataBatch
from app.modules.comments.models import Comment
from app.modules.media.service import asset_out
from app.modules.moderation.models import Report
from app.modules.posts.models import Post
from app.modules.users.models import AuditLog, User

QUEUES = ("default", "media", "ai")


class DayCount(BaseModel):
    day: date
    count: int


class NamedCount(BaseModel):
    name: str
    count: int


class TopPost(BaseModel):
    id: uuid.UUID
    author: str
    caption: str
    thumbnail: str | None
    likes: int
    comments: int
    views: int


class Dashboard(BaseModel):
    days: int
    users: int
    new_users: int
    posts: int
    new_posts: int
    comments: int
    new_comments: int
    likes: int
    views: int
    open_reports: int
    new_reports: int
    resolved_reports: int
    median_resolve_hours: float | None
    test_accounts: int
    users_by_day: list[DayCount]
    posts_by_day: list[DayCount]
    comments_by_day: list[DayCount]
    reports_by_day: list[DayCount]
    reports_by_reason: list[NamedCount]
    reports_by_type: list[NamedCount]
    top_posts: list[TopPost]


class StaffRow(BaseModel):
    username: str
    role: str
    status: str
    mfa: bool
    actions: int
    last_action_at: datetime | None


class Platform(BaseModel):
    days: int
    users_by_status: list[NamedCount]
    users_by_role: list[NamedCount]
    staff: list[StaffRow]
    staff_without_mfa: int
    failed_logins_24h: int
    token_reuse_7d: int
    live_test_batches: int
    database_ok: bool
    redis_ok: bool
    queue_depth: list[NamedCount]


class AuditRow(BaseModel):
    id: uuid.UUID
    actor: str | None
    action: str
    target: str | None
    ip: str | None
    meta: dict[str, Any] | None
    created_at: datetime


def _since(days: int) -> datetime:
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return today - timedelta(days=days - 1)


def _fill(rows: dict[date, int], since: datetime, days: int) -> list[DayCount]:
    """Quiet days must appear as zero, or the chart shows a false trend."""
    start = since.date()
    return [DayCount(day=start + timedelta(days=i), count=rows.get(start + timedelta(days=i), 0)) for i in range(days)]


async def _daily(s: AsyncSession, column: InstrumentedAttribute[Any], since: datetime, *where: Any) -> dict[date, int]:
    day = cast(func.timezone("UTC", column), Date)
    q = select(day, func.count()).where(column >= since, *where).group_by(day)
    return {r[0]: r[1] for r in await s.execute(q)}


async def _named(s: AsyncSession, column: InstrumentedAttribute[Any], *where: Any) -> list[NamedCount]:
    q = select(column, func.count()).where(*where).group_by(column).order_by(func.count().desc(), column)
    return [NamedCount(name=str(r[0]), count=r[1]) for r in await s.execute(q)]


def _thumbnail(post: Post) -> str | None:
    if not post.media:
        return None
    asset = asset_out(post.media[0].asset)
    return asset.images[0].webp if asset.images else asset.poster


async def dashboard(s: AsyncSession, days: int) -> Dashboard:
    since = _since(days)
    real_user = User.test_batch_id.is_(None)
    live_post = (Post.deleted_at.is_(None), Post.status == "published", Post.author_id.in_(select(User.id).where(real_user)))
    live_comment = (
        Comment.deleted_at.is_(None), Comment.held.is_(False), Comment.author_id.in_(select(User.id).where(real_user)),
    )

    async def scalar(q: Any) -> int:
        return int((await s.execute(q)).scalar_one() or 0)

    users_day = await _daily(s, User.created_at, since, real_user)
    posts_day = await _daily(s, Post.created_at, since, *live_post)
    comments_day = await _daily(s, Comment.created_at, since, *live_comment)
    reports_day = await _daily(s, Report.created_at, since)
    median = (await s.execute(
        select(func.percentile_cont(0.5).within_group(func.extract("epoch", Report.resolved_at - Report.created_at)))
        .where(Report.resolved_at >= since)
    )).scalar_one()
    top = (await s.execute(
        select(Post).where(*live_post, Post.created_at >= since)
        .order_by((Post.like_count + 2 * Post.comment_count + 3 * Post.save_count).desc(), Post.id.desc()).limit(5)
    )).scalars().unique().all()
    return Dashboard(
        days=days,
        users=await scalar(select(func.count()).select_from(User).where(real_user)),
        new_users=sum(users_day.values()),
        posts=await scalar(select(func.count()).select_from(Post).where(*live_post)),
        new_posts=sum(posts_day.values()),
        comments=await scalar(select(func.count()).select_from(Comment).where(*live_comment)),
        new_comments=sum(comments_day.values()),
        likes=await scalar(select(func.sum(Post.like_count)).where(*live_post)),
        views=await scalar(select(func.sum(Post.view_count)).where(*live_post)),
        open_reports=await scalar(select(func.count()).select_from(Report).where(Report.status == "open")),
        new_reports=sum(reports_day.values()),
        resolved_reports=await scalar(select(func.count()).select_from(Report).where(Report.resolved_at >= since)),
        median_resolve_hours=round(float(median) / 3600, 1) if median is not None else None,
        test_accounts=await scalar(select(func.count()).select_from(User).where(User.test_batch_id.is_not(None))),
        users_by_day=_fill(users_day, since, days),
        posts_by_day=_fill(posts_day, since, days),
        comments_by_day=_fill(comments_day, since, days),
        reports_by_day=_fill(reports_day, since, days),
        reports_by_reason=await _named(s, Report.reason, Report.created_at >= since),
        reports_by_type=await _named(s, Report.entity_type, Report.created_at >= since),
        top_posts=[
            TopPost(
                id=p.id, author=p.author.username, caption=p.caption[:120], thumbnail=_thumbnail(p),
                likes=p.like_count, comments=p.comment_count, views=p.view_count,
            ) for p in top
        ],
    )


async def _services_ok(s: AsyncSession) -> tuple[bool, bool, list[NamedCount]]:
    """A failed check is itself the answer, so the page still loads when a service is down."""
    database_ok = redis_ok = True
    depth: list[NamedCount] = []
    try:
        await s.execute(select(1))
    except Exception:  # noqa: BLE001
        database_ok = False
    try:
        client = get_redis()
        depth = [NamedCount(name=q, count=await client.llen(q)) for q in QUEUES]
    except Exception:  # noqa: BLE001
        redis_ok = False
    return database_ok, redis_ok, depth


async def platform(s: AsyncSession, days: int) -> Platform:
    since = _since(days)
    now = datetime.now(UTC)
    real_user = User.test_batch_id.is_(None)
    staff_rows = (await s.execute(
        select(User).where(User.role.in_(["staff", "admin", "superadmin"])).order_by(User.role.desc(), User.username)
    )).scalars().unique().all()
    activity = {
        r[0]: (r[1], r[2]) for r in await s.execute(
            select(AuditLog.actor_id, func.count(), func.max(AuditLog.created_at))
            .where(
                or_(AuditLog.action.like("admin.%"), AuditLog.action.like("staff.%")),
                AuditLog.created_at >= since, AuditLog.actor_id.is_not(None),
            )
            .group_by(AuditLog.actor_id)
        )
    }

    async def actions(name: str, after: datetime) -> int:
        q = select(func.count()).select_from(AuditLog).where(AuditLog.action == name, AuditLog.created_at >= after)
        return int((await s.execute(q)).scalar_one())

    database_ok, redis_ok, depth = await _services_ok(s)
    batches = select(func.count()).select_from(TestDataBatch).where(TestDataBatch.status == "ready")
    return Platform(
        days=days,
        users_by_status=await _named(s, User.status, real_user),
        users_by_role=await _named(s, User.role, real_user),
        staff=[
            StaffRow(
                username=u.username, role=u.role, status=u.status, mfa=u.totp_enabled,
                actions=activity.get(u.id, (0, None))[0], last_action_at=activity.get(u.id, (0, None))[1],
            ) for u in staff_rows
        ],
        staff_without_mfa=sum(1 for u in staff_rows if not u.totp_enabled),
        failed_logins_24h=await actions("auth.login_failed", now - timedelta(hours=24)),
        token_reuse_7d=await actions("auth.refresh_reuse", now - timedelta(days=7)),
        live_test_batches=int((await s.execute(batches)).scalar_one()),
        database_ok=database_ok, redis_ok=redis_ok, queue_depth=depth,
    )


async def audit_page(
    s: AsyncSession, category: str | None, cursor: uuid.UUID | None, limit: int
) -> Page[AuditRow]:
    q = select(AuditLog, User.username).outerjoin(User, User.id == AuditLog.actor_id)
    if category:
        q = q.where(AuditLog.action.like(f"{category}.%"))
    if cursor:
        q = q.where(AuditLog.id < cursor)
    rows = (await s.execute(q.order_by(AuditLog.id.desc()).limit(limit + 1))).all()
    more = len(rows) > limit
    rows = rows[:limit]
    return Page(
        items=[
            AuditRow(
                id=a.id, actor=name, action=a.action, target=a.target, ip=str(a.ip) if a.ip else None, meta=a.meta,
                created_at=a.created_at,
            ) for a, name in rows
        ],
        next_cursor=encode_cursor(rows[-1][0].id) if more else None,
    )
