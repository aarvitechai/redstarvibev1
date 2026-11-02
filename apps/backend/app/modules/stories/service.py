import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.safety.moderation import check_rules
from app.core.errors import bad_request, forbidden, not_found
from app.core.rate_limit import hit
from app.modules.media import repository as media_repo
from app.modules.media.service import asset_out
from app.modules.notifications.service import notify
from app.modules.stories import repository as repo
from app.modules.stories.models import Highlight, Story
from app.modules.stories.schemas import (
    HighlightIn,
    HighlightOut,
    StickerOut,
    StoryActivity,
    StoryGroup,
    StoryIn,
    StoryOut,
)
from app.modules.users import repository as user_repo
from app.modules.users import service as users
from app.modules.users.models import User
from app.modules.users.schemas import UserBrief


def _sticker(story: Story, viewer_id: uuid.UUID | None, mine: int | None, counts: dict[int, int]) -> StickerOut | None:
    data = story.sticker
    if not data:
        return None
    reveal = mine is not None or story.author_id == viewer_id
    return StickerOut(
        kind=data["kind"], question=data["question"], options=data["options"], my_answer=mine,
        counts=[counts.get(i, 0) for i in range(len(data["options"]))] if reveal else None,
        correct=data.get("correct") if reveal else None,
    )


async def _outs(s: AsyncSession, viewer: User | None, stories: list[Story], viewed_all: bool = False) -> list[StoryOut]:
    ids = [x.id for x in stories]
    viewer_id = viewer.id if viewer else None
    viewed = await repo.viewed_among(s, viewer.id, ids) if viewer else set()
    reactions = await repo.my_reactions(s, viewer.id, ids) if viewer else {}
    answers = await repo.my_answers(s, viewer.id, ids) if viewer else {}
    counts = await repo.answer_counts(s, [x.id for x in stories if x.sticker])
    return [
        StoryOut(
            id=x.id, author=users.brief(x.author), media=asset_out(x.asset), created_at=x.created_at,
            expires_at=x.expires_at, view_count=x.view_count, viewed=viewed_all or x.id in viewed,
            audience=x.audience, frame=x.frame, my_reaction=reactions.get(x.id),
            sticker=_sticker(x, viewer_id, answers.get(x.id), counts.get(x.id, {})),
        ) for x in stories
    ]


async def create(s: AsyncSession, user: User, data: StoryIn) -> StoryOut:
    await hit(f"story:user:{user.id}", 50, 86400)
    asset = await media_repo.get(s, data.asset_id)
    if asset is None or asset.owner_id != user.id:
        raise not_found("Upload")
    if asset.status != "ready" or asset.purpose != "story":
        raise bad_request("media_not_ready", "That upload is not ready yet")
    if data.sticker and check_rules(" ".join([data.sticker.question, *data.sticker.options])).blocked:
        raise bad_request("blocked_text", "That text is not allowed")
    story = Story(
        author_id=user.id, asset_id=asset.id, media_key=asset.raw_key,
        expires_at=datetime.now(UTC) + timedelta(hours=24), audience=data.audience, frame=data.frame,
        sticker=data.sticker.model_dump() if data.sticker else None,
    )
    await repo.add(s, story)
    await s.commit()
    story = await repo.get(s, story.id)  # type: ignore[assignment]
    return (await _outs(s, user, [story]))[0]


async def feed(s: AsyncSession, viewer: User) -> list[StoryGroup]:
    stories = await repo.feed(s, viewer.id)
    groups: dict[uuid.UUID, list[StoryOut]] = {}
    for out in await _outs(s, viewer, stories):
        groups.setdefault(out.author.id, []).append(out)
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
    if story.audience == "close_friends" and story.author_id != viewer.id:
        if not await repo.is_close_friend(s, story.author_id, viewer.id):
            raise not_found("Story")
    if story.expires_at < datetime.now(UTC) and story.author_id != viewer.id:
        raise not_found("Story")
    return story


async def by_user(s: AsyncSession, viewer: User, username: str) -> list[StoryOut]:
    user = await users.get_visible_user(s, viewer, username)
    if not await users.can_view_content_of(s, viewer, user):
        raise forbidden("This account is private")
    return await _outs(s, viewer, await repo.by_author(s, user.id, viewer.id))


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


async def react(s: AsyncSession, me: User, story_id: uuid.UUID, emoji: str) -> None:
    await hit(f"story_react:user:{me.id}", 300, 3600)
    story = await _viewable(s, me, story_id)
    if story.author_id == me.id:
        raise bad_request("own_story", "You cannot react to your own story")
    await repo.set_reaction(s, story.id, me.id, emoji)
    await s.commit()
    await notify(s, story.author_id, "story_reaction", me.id, story.id)


async def unreact(s: AsyncSession, me: User, story_id: uuid.UUID) -> None:
    await repo.remove_reaction(s, story_id, me.id)
    await s.commit()


async def answer(s: AsyncSession, me: User, story_id: uuid.UUID, option: int) -> StoryOut:
    story = await _viewable(s, me, story_id)
    if not story.sticker or story.author_id == me.id or option >= len(story.sticker["options"]):
        raise bad_request("invalid_answer", "That answer is not valid")
    await repo.add_answer(s, story.id, me.id, option)  # the first answer stands
    await s.commit()
    return (await _outs(s, me, [story]))[0]


async def activity(s: AsyncSession, me: User, story_id: uuid.UUID) -> list[StoryActivity]:
    story = await repo.get(s, story_id)
    if story is None:
        raise not_found("Story")
    if story.author_id != me.id:
        raise forbidden("Only the author can see this")
    return [StoryActivity(user=users.brief(u), reaction=r, answer=a) for u, r, a in await repo.activity(s, story_id)]


async def close_friends(s: AsyncSession, me: User) -> list[UserBrief]:
    return [users.brief(u) for u in await repo.close_friends(s, me.id)]


async def add_close_friend(s: AsyncSession, me: User, username: str) -> None:
    other = await user_repo.by_username(s, username.strip().lstrip("@"))
    if other is None or other.id == me.id or await user_repo.is_blocked_either_way(s, me.id, other.id):
        raise bad_request("invalid_friend", "That person cannot be added")
    await repo.add_close_friend(s, me.id, other.id)
    await s.commit()


async def remove_close_friend(s: AsyncSession, me: User, friend_id: uuid.UUID) -> None:
    await repo.remove_close_friend(s, me.id, friend_id)
    await s.commit()


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
    return await _hl(s, me, highlight, stories)


async def _hl(s: AsyncSession, viewer: User | None, h: Highlight, stories: list[Story]) -> HighlightOut:
    return HighlightOut(
        id=h.id, title=h.title, cover=asset_out(stories[0].asset) if stories else None,
        stories=await _outs(s, viewer, stories, viewed_all=True),
    )


async def highlights(s: AsyncSession, viewer: User | None, username: str) -> list[HighlightOut]:
    user = await users.get_visible_user(s, viewer, username)
    if not await users.can_view_content_of(s, viewer, user):
        raise forbidden("This account is private")
    rows = await repo.highlights_of(s, user.id, viewer.id if viewer else None)
    return [await _hl(s, viewer, h, st) for h, st in rows]


async def delete_highlight(s: AsyncSession, me: User, highlight_id: uuid.UUID) -> None:
    h = await repo.highlight(s, highlight_id)
    if h is None or h.user_id != me.id:
        raise not_found("Highlight")
    await repo.remove_highlight(s, highlight_id)
    await s.commit()
