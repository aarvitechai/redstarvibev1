import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import and_, delete, exists, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.follows.models import Follow
from app.modules.stories.models import Highlight, HighlightStory, Story, StoryView
from app.modules.users.models import Block, User


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
    q = (
        select(Story).join(User, User.id == Story.author_id)
        .where(Story.expires_at > datetime.now(UTC), User.status == "active", ~blocked,
               or_(Story.author_id == viewer, followed))
        .order_by(Story.id.asc()).limit(500)
    )
    return list((await s.execute(q)).scalars().unique())


async def by_author(s: AsyncSession, author: uuid.UUID) -> list[Story]:
    q = select(Story).where(Story.author_id == author, Story.expires_at > datetime.now(UTC)).order_by(Story.id.asc())
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


async def add_highlight(s: AsyncSession, highlight: Highlight, story_ids: Sequence[uuid.UUID]) -> None:
    s.add(highlight)
    await s.flush()
    for sid in story_ids:
        s.add(HighlightStory(highlight_id=highlight.id, story_id=sid))


async def owned_stories(s: AsyncSession, owner: uuid.UUID, ids: Sequence[uuid.UUID]) -> list[Story]:
    q = select(Story).where(Story.author_id == owner, Story.id.in_(ids))
    return list((await s.execute(q)).scalars().unique())


async def highlights_of(s: AsyncSession, user_id: uuid.UUID) -> list[tuple[Highlight, list[Story]]]:
    hs = list((await s.execute(
        select(Highlight).where(Highlight.user_id == user_id).order_by(Highlight.id.desc())
    )).scalars())
    result = []
    for h in hs:
        q = select(Story).join(HighlightStory, HighlightStory.story_id == Story.id).where(
            HighlightStory.highlight_id == h.id
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
