"""Profile rules and the view policy used by every module (owner, follower, blocked, private)."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.core.errors import bad_request, forbidden, not_found
from app.core.permissions import permissions_of
from app.core.security import encrypt_field
from app.core.storage import public_url
from app.modules.follows import repository as follow_repo
from app.modules.users import repository as repo
from app.modules.users.models import User
from app.modules.users.schemas import MeOut, ProfileOut, ProfileUpdate, UserBrief


def avatar_url(user: User) -> str | None:
    return public_url(user.profile.avatar_key) if user.profile else None


def brief(user: User) -> UserBrief:
    return UserBrief(
        id=user.id, username=user.username,
        display_name=(user.profile.display_name if user.profile else "") or user.username,
        avatar_url=avatar_url(user), verified=user.verified,
    )


async def can_view_content_of(s: AsyncSession, viewer: User | None, author: User) -> bool:
    """A blocked viewer sees nothing. A private account is visible only to active followers."""
    if author.status != "active" and not (viewer and viewer.id == author.id):
        return False
    if viewer is None:
        return not author.is_private
    if viewer.id == author.id:
        return True
    if await repo.is_blocked_either_way(s, viewer.id, author.id):
        return False
    if not author.is_private:
        return True
    return await follow_repo.status_of(s, viewer.id, author.id) == "active"


async def get_visible_user(s: AsyncSession, viewer: User | None, username: str) -> User:
    user = await repo.by_username(s, username)
    if user is None or user.status not in {"active"} and not (viewer and viewer.id == user.id):
        raise not_found("User")
    if viewer and viewer.id != user.id and await repo.has_blocked(s, user.id, viewer.id):
        raise not_found("User")
    return user


async def profile_out(s: AsyncSession, viewer: User | None, user: User) -> ProfileOut:
    is_self = bool(viewer and viewer.id == user.id)
    follow_status, follows_you, is_blocked, is_muted, is_restricted = None, False, False, False, False
    if viewer and not is_self:
        follow_status = await follow_repo.status_of(s, viewer.id, user.id)
        follows_you = await follow_repo.status_of(s, user.id, viewer.id) == "active"
        is_blocked = await repo.has_blocked(s, viewer.id, user.id)
        is_muted = await repo.has_limit(s, viewer.id, user.id, "mute")
        is_restricted = await repo.has_limit(s, viewer.id, user.id, "restrict")
    from app.modules.stories import repository as stories_repo

    can_view = await can_view_content_of(s, viewer, user)
    return ProfileOut(
        **brief(user).model_dump(),
        bio=user.profile.bio, website=user.profile.website, is_private=user.is_private,
        follower_count=user.follower_count, following_count=user.following_count, post_count=user.post_count,
        is_self=is_self, follow_status=follow_status, follows_you=follows_you, is_blocked=is_blocked,
        is_muted=is_muted, is_restricted=is_restricted,
        can_view_posts=can_view,
        has_active_story=can_view and await stories_repo.has_active(s, user.id),
    )


async def me_out(s: AsyncSession, user: User) -> MeOut:
    base = await profile_out(s, user, user)
    return MeOut(
        **base.model_dump(), email=user.email, role=user.role, status=user.status,
        totp_enabled=user.totp_enabled, delete_after=user.delete_after,
        hidden_words=user.profile.hidden_words or [], permissions=sorted(permissions_of(user.role)),
    )


async def update_profile(s: AsyncSession, user: User, data: ProfileUpdate) -> MeOut:
    if data.display_name is not None:
        user.profile.display_name = data.display_name.strip()
    if data.bio is not None:
        user.profile.bio = data.bio
    if "website" in data.model_fields_set:
        user.profile.website = str(data.website) if data.website else None
    if data.phone is not None:
        user.phone_encrypted = encrypt_field(data.phone) if data.phone else None
    if data.hidden_words is not None:
        user.profile.hidden_words = sorted({w.strip().lower() for w in data.hidden_words if w.strip()})
    if data.avatar_asset_id is not None:
        asset = await repo.ready_avatar(s, data.avatar_asset_id, user.id)
        if asset is None or not asset.variants:
            raise bad_request("avatar_not_ready", "That image is not ready yet")
        user.profile.avatar_key = asset.variants["images"][-1]["webp"]
    if data.is_private is not None and data.is_private != user.is_private:
        user.is_private = data.is_private
        if not data.is_private:
            await follow_repo.accept_all_pending(s, user.id)
    await s.commit()
    return await me_out(s, user)


async def block(s: AsyncSession, me: User, username: str) -> None:
    other = await repo.by_username(s, username)
    if other is None:
        raise not_found("User")
    if other.id == me.id:
        raise bad_request("invalid_target", "You cannot block yourself")
    await repo.add_block(s, me.id, other.id)
    removed = await follow_repo.remove_both_directions(s, me.id, other.id)
    for follower, followee in removed:
        await repo.bump_counts(s, follower, following_count=-1)
        await repo.bump_counts(s, followee, follower_count=-1)
    await s.commit()
    pipe = get_redis().pipeline()
    pipe.delete(f"feed:{me.id}")
    pipe.delete(f"feed:{other.id}")
    await pipe.execute()


async def unblock(s: AsyncSession, me: User, username: str) -> None:
    other = await repo.by_username(s, username)
    if other is None:
        raise not_found("User")
    await repo.remove_block(s, me.id, other.id)
    await s.commit()


async def set_limit(s: AsyncSession, me: User, username: str, kind: str, on: bool) -> None:
    other = await repo.by_username(s, username)
    if other is None:
        raise not_found("User")
    if other.id == me.id:
        raise bad_request("invalid_target", "You cannot do this to yourself")
    if on:
        await repo.add_limit(s, me.id, other.id, kind)
    else:
        await repo.remove_limit(s, me.id, other.id, kind)
    await s.commit()


async def request_deletion(s: AsyncSession, user: User) -> None:
    await repo.schedule_deletion(s, user)
    await repo.audit(s, user.id, "account.delete_requested", str(user.id))
    await s.commit()


async def cancel_deletion(s: AsyncSession, user: User) -> None:
    if user.status != "deleting":
        raise forbidden("This account is not scheduled for deletion")
    user.status, user.delete_after = "active", None
    await repo.audit(s, user.id, "account.delete_cancelled", str(user.id))
    await s.commit()


async def uid_list(s: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, User]:
    return await repo.by_ids(s, ids)
