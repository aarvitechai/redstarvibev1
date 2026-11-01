import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import bad_request, forbidden, not_found
from app.core.rate_limit import hit
from app.modules.media import repository as media_repo
from app.modules.media.service import asset_out
from app.modules.stories import repository as repo
from app.modules.stories.models import Highlight, Story
from app.modules.stories.schemas import HighlightIn, HighlightOut, StoryGroup, StoryOut
from app.modules.users import service as users
from app.modules.users.models import User
from app.modules.users.schemas import UserBrief


def _out(story: Story, viewed: bool) -> StoryOut:
    return StoryOut(
        id=story.id, author=users.brief(story.author), media=asset_out(story.asset), created_at=story.created_at,
        expires_at=story.expires_at, view_count=story.view_count, viewed=viewed,
    )


async def create(s: AsyncSession, user: User, asset_id: uuid.UUID) -> StoryOut:
    await hit(f"story:user:{user.id}", 50, 86400)
    asset = await media_repo.get(s, asset_id)
    if asset is None or asset.owner_id != user.id:
        raise not_found("Upload")
    if asset.status != "ready" or asset.purpose != "story":
        raise bad_request("media_not_ready", "That upload is not ready yet")
    story = Story(
        author_id=user.id, asset_id=asset.id, media_key=asset.raw_key,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    await repo.add(s, story)
    await s.commit()
    story = await repo.get(s, story.id)  # type: ignore[assignment]
    return _out(story, False)


async def feed(s: AsyncSession, viewer: User) -> list[StoryGroup]:
    stories = await repo.feed(s, viewer.id)
    viewed = await repo.viewed_among(s, viewer.id, [x.id for x in stories])
    groups: dict[uuid.UUID, list[StoryOut]] = {}
    for story in stories:
        groups.setdefault(story.author_id, []).append(_out(story, story.id in viewed))
    result = [
        StoryGroup(author=items[0].author, stories=items, all_viewed=all(i.viewed for i in items))
        for items in groups.values()
    ]
    result.sort(key=lambda g: (g.author.id != viewer.id, g.all_viewed, -g.stories[-1].created_at.timestamp()))
    return result


async def _viewable(s: AsyncSession, viewer: User, story_id: uuid.UUID) -> Story:
    story = await repo.get(s, story_id)
    if story is None or not await users.can_view_content_of(s, viewer, story.author):
        raise not_found("Story")
    if story.expires_at < datetime.now(UTC) and story.author_id != viewer.id:
        raise not_found("Story")
    return story


async def by_user(s: AsyncSession, viewer: User, username: str) -> list[StoryOut]:
    user = await users.get_visible_user(s, viewer, username)
    if not await users.can_view_content_of(s, viewer, user):
        raise forbidden("This account is private")
    stories = await repo.by_author(s, user.id)
    viewed = await repo.viewed_among(s, viewer.id, [x.id for x in stories])
    return [_out(x, x.id in viewed) for x in stories]


async def view(s: AsyncSession, viewer: User, story_id: uuid.UUID) -> None:
    story = await _viewable(s, viewer, story_id)
    if story.author_id != viewer.id:
        await repo.add_view(s, story.id, viewer.id)
        await s.commit()


async def viewers(s: AsyncSession, me: User, story_id: uuid.UUID) -> list[UserBrief]:
    story = await repo.get(s, story_id)
    if story is None:
        raise not_found("Story")
    if story.author_id != me.id:
        raise forbidden("Only the author can see viewers")
    return [users.brief(u) for u in await repo.viewers(s, story_id)]


async def delete(s: AsyncSession, me: User, story_id: uuid.UUID) -> None:
    story = await repo.get(s, story_id)
    if story is None:
        raise not_found("Story")
    if story.author_id != me.id:
        raise forbidden("This is not your story")
    await repo.remove(s, story_id)
    await s.commit()


async def create_highlight(s: AsyncSession, me: User, data: HighlightIn) -> HighlightOut:
    stories = await repo.owned_stories(s, me.id, data.story_ids)
    if len(stories) != len(set(data.story_ids)):
        raise not_found("Story")
    highlight = Highlight(user_id=me.id, title=data.title.strip())
    await repo.add_highlight(s, highlight, data.story_ids)
    await s.commit()
    return _hl(highlight, stories)


def _hl(h: Highlight, stories: list[Story]) -> HighlightOut:
    return HighlightOut(
        id=h.id, title=h.title, cover=asset_out(stories[0].asset) if stories else None,
        stories=[_out(x, True) for x in stories],
    )


async def highlights(s: AsyncSession, viewer: User | None, username: str) -> list[HighlightOut]:
    user = await users.get_visible_user(s, viewer, username)
    if not await users.can_view_content_of(s, viewer, user):
        raise forbidden("This account is private")
    return [_hl(h, st) for h, st in await repo.highlights_of(s, user.id)]


async def delete_highlight(s: AsyncSession, me: User, highlight_id: uuid.UUID) -> None:
    h = await repo.highlight(s, highlight_id)
    if h is None or h.user_id != me.id:
        raise not_found("Highlight")
    await repo.remove_highlight(s, highlight_id)
    await s.commit()
