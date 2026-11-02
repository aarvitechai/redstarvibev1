"""Public groups with members and their own posts. Anyone can read and join. Only members can post."""
import re
import secrets
import uuid
from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.safety.moderation import check_rules
from app.core.errors import bad_request, forbidden, not_found
from app.core.pagination import Page, encode_cursor
from app.core.rate_limit import hit
from app.modules.communities.models import Community, CommunityMember, CommunityPost
from app.modules.media import repository as media_repo
from app.modules.media.schemas import AssetOut
from app.modules.media.service import asset_out
from app.modules.search.repository import _escape
from app.modules.users import repository as users
from app.modules.users import service as user_service
from app.modules.users.models import User
from app.modules.users.schemas import UserBrief


class CommunityIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=80)]
    description: str = Field("", max_length=500)


class CommunityOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    description: str
    member_count: int
    is_member: bool = False
    is_owner: bool = False


class CommunityPostIn(BaseModel):
    body: str = Field("", max_length=4000)
    asset_id: uuid.UUID | None = None


class CommunityPostOut(BaseModel):
    id: uuid.UUID
    author: UserBrief
    body: str
    media: AssetOut | None
    created_at: datetime
    can_delete: bool = False


def _slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "community"
    return f"{base}-{secrets.token_hex(3)}"


def _check_text(*texts: str) -> None:
    if check_rules(" ".join(texts)).blocked:
        raise bad_request("blocked_text", "That text is not allowed")


async def _count(s: AsyncSession, community_id: uuid.UUID) -> int:
    q = select(func.count()).select_from(CommunityMember).where(CommunityMember.community_id == community_id)
    return int((await s.execute(q)).scalar_one())


async def _is_member(s: AsyncSession, community_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    return await s.get(CommunityMember, (community_id, user_id)) is not None


async def _out(s: AsyncSession, c: Community, viewer: User | None) -> CommunityOut:
    return CommunityOut(
        id=c.id, slug=c.slug, name=c.name, description=c.description, member_count=await _count(s, c.id),
        is_member=bool(viewer and await _is_member(s, c.id, viewer.id)), is_owner=bool(viewer and viewer.id == c.owner_id),
    )


async def _by_slug(s: AsyncSession, slug: str) -> Community:
    row = (await s.execute(select(Community).where(Community.slug == slug))).scalar_one_or_none()
    if row is None:
        raise not_found("Community")
    return row


async def create(s: AsyncSession, me: User, data: CommunityIn) -> CommunityOut:
    await hit(f"community:user:{me.id}", 5, 86400)
    description = data.description.strip()
    _check_text(data.name, description)
    community = Community(slug=_slug(data.name), name=data.name, description=description, owner_id=me.id)
    s.add(community)
    await s.flush()
    s.add(CommunityMember(community_id=community.id, user_id=me.id))
    await s.commit()
    return await _out(s, community, me)


async def browse(s: AsyncSession, viewer: User | None, q: str, mine: bool) -> list[CommunityOut]:
    stmt = select(Community)
    if q:
        stmt = stmt.where(Community.name.ilike(f"%{_escape(q)}%", escape="\\"))
    if mine:
        if viewer is None:
            return []
        joined = CommunityMember.community_id == Community.id
        stmt = stmt.join(CommunityMember, joined).where(CommunityMember.user_id == viewer.id)
    rows = (await s.execute(stmt.order_by(Community.id.desc()).limit(50))).scalars()
    return [await _out(s, c, viewer) for c in rows]


async def get(s: AsyncSession, viewer: User | None, slug: str) -> CommunityOut:
    return await _out(s, await _by_slug(s, slug), viewer)


async def join(s: AsyncSession, me: User, slug: str) -> CommunityOut:
    await hit(f"community_join:user:{me.id}", 60, 3600)
    community = await _by_slug(s, slug)
    if await users.is_blocked_either_way(s, me.id, community.owner_id):
        raise not_found("Community")
    await s.execute(insert(CommunityMember).values(community_id=community.id, user_id=me.id).on_conflict_do_nothing())
    await s.commit()
    return await _out(s, community, me)


async def leave(s: AsyncSession, me: User, slug: str) -> CommunityOut:
    community = await _by_slug(s, slug)
    if community.owner_id == me.id:
        raise bad_request("owner_cannot_leave", "The owner cannot leave. Delete the community instead.")
    await s.execute(delete(CommunityMember).where(CommunityMember.community_id == community.id, CommunityMember.user_id == me.id))
    await s.commit()
    return await _out(s, community, me)


async def delete_community(s: AsyncSession, me: User, slug: str) -> None:
    community = await _by_slug(s, slug)
    if community.owner_id != me.id:
        raise forbidden("Only the owner can delete this community")
    await s.delete(community)
    await s.commit()


async def members(s: AsyncSession, slug: str) -> list[UserBrief]:
    community = await _by_slug(s, slug)
    q = (
        select(User).join(CommunityMember, CommunityMember.user_id == User.id)
        .where(CommunityMember.community_id == community.id, User.status == "active").order_by(User.username).limit(200)
    )
    return [user_service.brief(u) for u in (await s.execute(q)).scalars().unique()]


async def remove_member(s: AsyncSession, me: User, slug: str, user_id: uuid.UUID) -> None:
    community = await _by_slug(s, slug)
    if community.owner_id != me.id:
        raise forbidden("Only the owner can remove members")
    if user_id == me.id:
        raise bad_request("owner_cannot_leave", "The owner cannot be removed")
    await s.execute(delete(CommunityMember).where(
        CommunityMember.community_id == community.id, CommunityMember.user_id == user_id
    ))
    await s.commit()


def _post_out(post: CommunityPost, viewer: User | None, owner_id: uuid.UUID) -> CommunityPostOut:
    return CommunityPostOut(
        id=post.id, author=user_service.brief(post.author), body=post.body, created_at=post.created_at,
        media=asset_out(post.asset) if post.asset else None,
        can_delete=bool(viewer and viewer.id in {post.author_id, owner_id}),
    )


async def add_post(s: AsyncSession, me: User, slug: str, data: CommunityPostIn) -> CommunityPostOut:
    await hit(f"community_post:user:{me.id}", 60, 3600)
    community = await _by_slug(s, slug)
    if not await _is_member(s, community.id, me.id):
        raise forbidden("Join this community to post")
    body = data.body.strip()
    if not body and not data.asset_id:
        raise bad_request("empty_post", "Write something first")
    _check_text(body)
    if data.asset_id:
        asset = await media_repo.get(s, data.asset_id)
        if asset is None or asset.owner_id != me.id or asset.status != "ready":
            raise bad_request("invalid_media", "That upload cannot be used")
        if asset.purpose != "post" or asset.kind != "image":
            raise bad_request("invalid_media", "That upload cannot be used")
    post = CommunityPost(community_id=community.id, author_id=me.id, body=body, asset_id=data.asset_id)
    s.add(post)
    await s.commit()
    row = await _post(s, post.id)
    return _post_out(row, me, community.owner_id)  # type: ignore[arg-type]


async def _post(s: AsyncSession, post_id: uuid.UUID) -> CommunityPost | None:
    q = select(CommunityPost).where(CommunityPost.id == post_id, CommunityPost.deleted_at.is_(None))
    return (await s.execute(q.execution_options(populate_existing=True))).scalars().first()


async def list_posts(
    s: AsyncSession, viewer: User | None, slug: str, cursor: uuid.UUID | None, limit: int
) -> Page[CommunityPostOut]:
    community = await _by_slug(s, slug)
    q = select(CommunityPost).join(User, User.id == CommunityPost.author_id).where(
        CommunityPost.community_id == community.id, CommunityPost.deleted_at.is_(None), User.status == "active"
    )
    if viewer:
        blocked = await users.blocked_ids(s, viewer.id)
        if blocked:
            q = q.where(CommunityPost.author_id.not_in(blocked))
    if cursor:
        q = q.where(CommunityPost.id < cursor)
    rows = list((await s.execute(q.order_by(CommunityPost.id.desc()).limit(limit + 1))).scalars().unique())
    more = len(rows) > limit
    rows = rows[:limit]
    return Page(
        items=[_post_out(p, viewer, community.owner_id) for p in rows],
        next_cursor=encode_cursor(rows[-1].id) if more else None,
    )


async def delete_post(s: AsyncSession, me: User, post_id: uuid.UUID) -> None:
    post = await _post(s, post_id)
    if post is None:
        raise not_found("Post")
    community = await s.get(Community, post.community_id)
    if me.id != post.author_id and (community is None or community.owner_id != me.id):
        raise forbidden("You cannot delete this post")
    post.deleted_at = datetime.now(UTC)
    await s.commit()


async def get_post_for_report(s: AsyncSession, post_id: uuid.UUID) -> CommunityPost | None:
    return await _post(s, post_id)
