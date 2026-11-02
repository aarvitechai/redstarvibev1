import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, and_, delete, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.follows.models import Follow
from app.modules.stories.models import (
    CloseFriend,
    Highlight,
    HighlightStory,
    Story,
    StoryAnswer,
    StoryReaction,
    StoryView,
)
from app.modules.users.models import Block, User, UserLimit


def audience_clause(viewer: uuid.UUID | None) -> ColumnElement[bool]:
    """A close friends story reaches only its author and the people on their list."""
    if viewer is None:
        return Story.audience == "everyone"
    listed = exists().where(CloseFriend.user_id == Story.author_id, CloseFriend.friend_id == viewer)
    return or_(Story.audience == "everyone", Story.author_id == viewer, listed)


def _active() -> object:
    return Story.expires_at > datetime.now(UTC)


async def has_active(s: AsyncSession, user_id: uuid.UUID) -> bool:
    q = select(Story.id).where(Story.author_id == user_id, Story.expires_at > datetime.now(UTC)).limit(1)
    return (await s.execute(q)).first() is not None


async def add(s: AsyncSession, story: Story) -> None:
    s.add(story)
    await s.flush()
    await s.refresh(story, ["created_at"])


async def get(s: AsyncSession, story_id: uuid.UUID) -> Story | None:
    return (await s.execute(select(Story).where(Story.id == story_id))).scalars().first()


async def feed(s: AsyncSession, viewer: uuid.UUID) -> list[Story]:
    followed = exists().where(
        Follow.follower_id == viewer, Follow.followee_id == Story.author_id, Follow.status == "active"
    )
    blocked = exists().where(or_(
        and_(Block.blocker_id == viewer, Block.blocked_id == Story.author_id),
        and_(Block.blocker_id == Story.author_id, Block.blocked_id == viewer),
    ))
    muted = exists().where(UserLimit.user_id == viewer, UserLimit.target_id == Story.author_id, UserLimit.kind == "mute")
    q = (
        select(Story).join(User, User.id == Story.author_id)
        .where(Story.expires_at > datetime.now(UTC), User.status == "active", ~blocked, ~muted, audience_clause(viewer),
               or_(Story.author_id == viewer, followed))
        .order_by(Story.id.asc()).limit(500)
    )
    return list((await s.execute(q)).scalars().unique())


async def by_author(s: AsyncSession, author: uuid.UUID, viewer: uuid.UUID | None) -> list[Story]:
    q = select(Story).where(
        Story.author_id == author, Story.expires_at > datetime.now(UTC), audience_clause(viewer)
    ).order_by(Story.id.asc())
    return list((await s.execute(q)).scalars().unique())


async def viewed_among(s: AsyncSession, viewer: uuid.UUID, ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
    if not ids:
        return set()
    q = select(StoryView.story_id).where(StoryView.viewer_id == viewer, StoryView.story_id.in_(ids))
    return set((await s.execute(q)).scalars())


async def add_view(s: AsyncSession, story_id: uuid.UUID, viewer: uuid.UUID) -> None:
    res = await s.execute(
        insert(StoryView).values(story_id=story_id, viewer_id=viewer).on_conflict_do_nothing().returning(StoryView.story_id)
    )
    if res.first():
        await s.execute(update(Story).where(Story.id == story_id).values(view_count=Story.view_count + 1))


async def viewers(s: AsyncSession, story_id: uuid.UUID) -> list[User]:
    q = select(User).join(StoryView, StoryView.viewer_id == User.id).where(StoryView.story_id == story_id).limit(500)
    return list((await s.execute(q)).scalars().unique())


async def is_close_friend(s: AsyncSession, author: uuid.UUID, viewer: uuid.UUID) -> bool:
    return await s.get(CloseFriend, (author, viewer)) is not None


async def close_friends(s: AsyncSession, user_id: uuid.UUID) -> list[User]:
    q = select(User).join(CloseFriend, CloseFriend.friend_id == User.id).where(CloseFriend.user_id == user_id)
    return list((await s.execute(q.order_by(User.username))).scalars().unique())


async def add_close_friend(s: AsyncSession, user_id: uuid.UUID, friend_id: uuid.UUID) -> None:
    await s.execute(insert(CloseFriend).values(user_id=user_id, friend_id=friend_id).on_conflict_do_nothing())


async def remove_close_friend(s: AsyncSession, user_id: uuid.UUID, friend_id: uuid.UUID) -> None:
    await s.execute(delete(CloseFriend).where(CloseFriend.user_id == user_id, CloseFriend.friend_id == friend_id))


async def set_reaction(s: AsyncSession, story_id: uuid.UUID, user_id: uuid.UUID, emoji: str) -> None:
    stmt = insert(StoryReaction).values(story_id=story_id, user_id=user_id, emoji=emoji)
    await s.execute(stmt.on_conflict_do_update(index_elements=["story_id", "user_id"], set_={"emoji": emoji}))


async def remove_reaction(s: AsyncSession, story_id: uuid.UUID, user_id: uuid.UUID) -> None:
    await s.execute(delete(StoryReaction).where(StoryReaction.story_id == story_id, StoryReaction.user_id == user_id))


async def add_answer(s: AsyncSession, story_id: uuid.UUID, user_id: uuid.UUID, option: int) -> None:
    await s.execute(insert(StoryAnswer).values(story_id=story_id, user_id=user_id, option=option).on_conflict_do_nothing())


async def my_reactions(s: AsyncSession, viewer: uuid.UUID, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
    q = select(StoryReaction.story_id, StoryReaction.emoji).where(
        StoryReaction.user_id == viewer, StoryReaction.story_id.in_(ids)
    )
    return {r[0]: r[1] for r in await s.execute(q)} if ids else {}


async def my_answers(s: AsyncSession, viewer: uuid.UUID, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
    q = select(StoryAnswer.story_id, StoryAnswer.option).where(StoryAnswer.user_id == viewer, StoryAnswer.story_id.in_(ids))
    return {r[0]: r[1] for r in await s.execute(q)} if ids else {}


async def answer_counts(s: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, dict[int, int]]:
    if not ids:
        return {}
    q = select(StoryAnswer.story_id, StoryAnswer.option, func.count()).where(StoryAnswer.story_id.in_(ids))
    result: dict[uuid.UUID, dict[int, int]] = {}
    for story_id, option, count in await s.execute(q.group_by(StoryAnswer.story_id, StoryAnswer.option)):
        result.setdefault(story_id, {})[option] = count
    return result


async def activity(s: AsyncSession, story_id: uuid.UUID) -> list[tuple[User, str | None, int | None]]:
    reactions = {r[0]: r[1] for r in await s.execute(
        select(StoryReaction.user_id, StoryReaction.emoji).where(StoryReaction.story_id == story_id)
    )}
    answers = {r[0]: r[1] for r in await s.execute(
        select(StoryAnswer.user_id, StoryAnswer.option).where(StoryAnswer.story_id == story_id)
    )}
    ids = {*reactions, *answers}
    if not ids:
        return []
    people = (await s.execute(select(User).where(User.id.in_(ids)).order_by(User.username))).scalars().unique()
    return [(u, reactions.get(u.id), answers.get(u.id)) for u in people]


async def add_highlight(s: AsyncSession, highlight: Highlight, story_ids: Sequence[uuid.UUID]) -> None:
    s.add(highlight)
    await s.flush()
    for sid in story_ids:
        s.add(HighlightStory(highlight_id=highlight.id, story_id=sid))


async def owned_stories(s: AsyncSession, owner: uuid.UUID, ids: Sequence[uuid.UUID]) -> list[Story]:
    q = select(Story).where(Story.author_id == owner, Story.id.in_(ids))
    return list((await s.execute(q)).scalars().unique())


async def highlights_of(s: AsyncSession, user_id: uuid.UUID, viewer: uuid.UUID | None) -> list[tuple[Highlight, list[Story]]]:
    hs = list((await s.execute(
        select(Highlight).where(Highlight.user_id == user_id).order_by(Highlight.id.desc())
    )).scalars())
    result = []
    for h in hs:
        q = select(Story).join(HighlightStory, HighlightStory.story_id == Story.id).where(
            HighlightStory.highlight_id == h.id, audience_clause(viewer)
        ).order_by(Story.id.asc())
        result.append((h, list((await s.execute(q)).scalars().unique())))
    return result


async def highlight(s: AsyncSession, highlight_id: uuid.UUID) -> Highlight | None:
    return await s.get(Highlight, highlight_id)


async def remove_highlight(s: AsyncSession, highlight_id: uuid.UUID) -> None:
    await s.execute(delete(Highlight).where(Highlight.id == highlight_id))


async def remove(s: AsyncSession, story_id: uuid.UUID) -> None:
    await s.execute(delete(Story).where(Story.id == story_id))


async def purge_expired(s: AsyncSession) -> int:
    """Expired stories kept in a highlight stay; everything else is deleted."""
    kept = select(HighlightStory.story_id)
    res = await s.execute(
        delete(Story).where(Story.expires_at < datetime.now(UTC), Story.id.not_in(kept)).returning(Story.id)
    )
    return len(res.all())
