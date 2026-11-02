import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, Db, OptionalUser
from app.modules.stories import service
from app.modules.stories.schemas import (
    AnswerIn,
    CloseFriendIn,
    HighlightIn,
    HighlightOut,
    ReactIn,
    StoryActivity,
    StoryGroup,
    StoryIn,
    StoryOut,
)
from app.modules.users.schemas import UserBrief

router = APIRouter(tags=["stories"])


@router.post("/stories", response_model=StoryOut, status_code=201)
async def create(data: StoryIn, me: CurrentUser, s: Db) -> StoryOut:
    return await service.create(s, me, data)


@router.get("/stories/feed", response_model=list[StoryGroup])
async def feed(me: CurrentUser, s: Db) -> list[StoryGroup]:
    return await service.feed(s, me)


@router.get("/users/{username}/stories", response_model=list[StoryOut])
async def by_user(username: str, me: CurrentUser, s: Db) -> list[StoryOut]:
    return await service.by_user(s, me, username)


@router.post("/stories/{story_id}/view", status_code=204)
async def view(story_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.view(s, me, story_id)


@router.get("/stories/{story_id}/viewers", response_model=list[UserBrief])
async def viewers(story_id: uuid.UUID, me: CurrentUser, s: Db) -> list[UserBrief]:
    return await service.viewers(s, me, story_id)


@router.post("/stories/{story_id}/react", status_code=204)
async def react(story_id: uuid.UUID, data: ReactIn, me: CurrentUser, s: Db) -> None:
    await service.react(s, me, story_id, data.emoji)


@router.delete("/stories/{story_id}/react", status_code=204)
async def unreact(story_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.unreact(s, me, story_id)


@router.post("/stories/{story_id}/answer", response_model=StoryOut)
async def answer(story_id: uuid.UUID, data: AnswerIn, me: CurrentUser, s: Db) -> StoryOut:
    return await service.answer(s, me, story_id, data.option)


@router.get("/stories/{story_id}/activity", response_model=list[StoryActivity])
async def activity(story_id: uuid.UUID, me: CurrentUser, s: Db) -> list[StoryActivity]:
    return await service.activity(s, me, story_id)


@router.get("/close-friends", response_model=list[UserBrief])
async def close_friends(me: CurrentUser, s: Db) -> list[UserBrief]:
    return await service.close_friends(s, me)


@router.post("/close-friends", status_code=204)
async def add_close_friend(data: CloseFriendIn, me: CurrentUser, s: Db) -> None:
    await service.add_close_friend(s, me, data.username)


@router.delete("/close-friends/{friend_id}", status_code=204)
async def remove_close_friend(friend_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.remove_close_friend(s, me, friend_id)


@router.delete("/stories/{story_id}", status_code=204)
async def delete(story_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.delete(s, me, story_id)


@router.post("/highlights", response_model=HighlightOut, status_code=201)
async def create_highlight(data: HighlightIn, me: CurrentUser, s: Db) -> HighlightOut:
    return await service.create_highlight(s, me, data)


@router.get("/users/{username}/highlights", response_model=list[HighlightOut])
async def highlights(username: str, viewer: OptionalUser, s: Db) -> list[HighlightOut]:
    return await service.highlights(s, viewer, username)


@router.delete("/highlights/{highlight_id}", status_code=204)
async def delete_highlight(highlight_id: uuid.UUID, me: CurrentUser, s: Db) -> None:
    await service.delete_highlight(s, me, highlight_id)
