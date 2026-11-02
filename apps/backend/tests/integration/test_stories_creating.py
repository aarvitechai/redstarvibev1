"""Close friends, reactions, polls, quizzes, frames, filters, collabs, pinning and time capsules."""
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from tests.integration.test_flows import OVERLAY, _ready_asset  # noqa: F401


async def _story_asset(owner_id):
    from app.core.database import SessionLocal
    from app.modules.media.models import MediaAsset

    async with SessionLocal() as s:
        asset = MediaAsset(
            owner_id=uuid.UUID(owner_id), purpose="story", kind="image", raw_key=f"{owner_id}/s", declared_type="image/jpeg",
            size_bytes=1, status="ready", width=10, height=10, variants={"images": [{"w": 10, "webp": "x.webp"}]},
        )
        s.add(asset)
        await s.commit()
        return str(asset.id)


async def _story(author, **extra):
    res = await author.post("/stories", json={"asset_id": await _story_asset(author.id)} | extra)
    assert res.status_code == 201, res.text
    return res.json()


async def _follow(follower, followee):
    await follower.post(f"/users/{followee.username}/follow")


async def _ids_in_feed(viewer):
    return [st["id"] for group in (await viewer.get("/stories/feed")).json() for st in group["stories"]]


async def test_close_friends_story_is_hidden_from_other_followers(make_user):
    author, friend, follower = await make_user(), await make_user(), await make_user()
    await _follow(friend, author)
    await _follow(follower, author)
    assert (await author.post("/close-friends", json={"username": friend.username})).status_code == 204
    story = await _story(author, audience="close_friends")
    assert story["id"] in await _ids_in_feed(friend)
    assert story["id"] not in await _ids_in_feed(follower)
    assert story["id"] in await _ids_in_feed(author)
    assert story["id"] not in [x["id"] for x in (await follower.get(f"/users/{author.username}/stories")).json()]
    assert (await follower.post(f"/stories/{story['id']}/view")).status_code == 404
    assert (await follower.post(f"/stories/{story['id']}/react", json={"emoji": "🔥"})).status_code == 404
    assert [u["username"] for u in (await author.get("/close-friends")).json()] == [friend.username]
    await author.delete(f"/close-friends/{friend.id}")
    assert story["id"] not in await _ids_in_feed(friend)


async def test_close_friends_story_stays_hidden_in_highlights(make_user):
    author, follower, friend = await make_user(), await make_user(), await make_user()
    await author.post("/close-friends", json={"username": friend.username})
    story = await _story(author, audience="close_friends")
    made = await author.post("/highlights", json={"title": "Mine", "story_ids": [story["id"]]})
    assert made.status_code == 201, made.text
    assert (await follower.get(f"/users/{author.username}/highlights")).json()[0]["stories"] == []
    assert len((await friend.get(f"/users/{author.username}/highlights")).json()[0]["stories"]) == 1


async def test_reactions_are_seen_by_the_author_only(make_user):
    author, fan = await make_user(), await make_user()
    story = await _story(author)
    assert (await fan.post(f"/stories/{story['id']}/react", json={"emoji": "<script>"})).status_code == 422
    assert (await fan.post(f"/stories/{story['id']}/react", json={"emoji": "🔥"})).status_code == 204
    assert (await fan.post(f"/stories/{story['id']}/react", json={"emoji": "😂"})).status_code == 204
    assert (await author.post(f"/stories/{story['id']}/react", json={"emoji": "🔥"})).status_code == 400
    activity = (await author.get(f"/stories/{story['id']}/activity")).json()
    assert [(a["user"]["username"], a["reaction"]) for a in activity] == [(fan.username, "😂")]
    assert (await fan.get(f"/stories/{story['id']}/activity")).status_code == 403
    assert (await fan.delete(f"/stories/{story['id']}/react")).status_code == 204
    assert (await author.get(f"/stories/{story['id']}/activity")).json() == []


async def test_poll_shows_results_only_after_answering(make_user):
    author, one, two = await make_user(), await make_user(), await make_user()
    story = await _story(author, sticker={"kind": "poll", "question": "Tea or coffee?", "options": ["Tea", "Coffee"]})
    assert story["sticker"]["counts"] == [0, 0]  # the author always sees results
    await _follow(one, author)
    before = (await one.get(f"/users/{author.username}/stories")).json()[0]["sticker"]
    assert before["counts"] is None and before["my_answer"] is None

    answered = await one.post(f"/stories/{story['id']}/answer", json={"option": 1})
    assert answered.json()["sticker"]["counts"] == [0, 1] and answered.json()["sticker"]["my_answer"] == 1
    again = await one.post(f"/stories/{story['id']}/answer", json={"option": 0})
    assert again.json()["sticker"]["counts"] == [0, 1]  # one vote each, and it cannot be changed
    assert (await two.post(f"/stories/{story['id']}/answer", json={"option": 3})).status_code == 400
    assert (await author.post(f"/stories/{story['id']}/answer", json={"option": 0})).status_code == 400
    assert (await author.get(f"/stories/{story['id']}/activity")).json()[0]["answer"] == 1


async def test_quiz_keeps_the_correct_answer_secret_until_answered(make_user):
    author, player = await make_user(), await make_user()
    body = {"kind": "quiz", "question": "Capital of India?", "options": ["Mumbai", "Delhi"], "correct": 1}
    story = await _story(author, sticker=body)
    assert story["sticker"]["correct"] == 1
    seen = (await player.get(f"/users/{author.username}/stories")).json()[0]["sticker"]
    assert seen["correct"] is None
    done = await player.post(f"/stories/{story['id']}/answer", json={"option": 0})
    assert done.json()["sticker"]["correct"] == 1


async def test_bad_stickers_and_frames_are_refused(make_user):
    author = await make_user()
    asset = await _story_asset(author.id)
    bad = [
        {"sticker": {"kind": "quiz", "question": "Q?", "options": ["a", "b"]}},
        {"sticker": {"kind": "quiz", "question": "Q?", "options": ["a", "b"], "correct": 5}},
        {"sticker": {"kind": "poll", "question": "Q?", "options": ["a"]}},
        {"sticker": {"kind": "poll", "question": "Q?", "options": ["a", "b"], "correct": 0}},
        {"frame": "unknown"},
        {"audience": "secret"},
    ]
    for extra in bad:
        assert (await author.post("/stories", json={"asset_id": asset} | extra)).status_code == 422, extra
    framed = await _story(author, frame="diwali")
    assert framed["frame"] == "diwali"


async def _post(author, **extra):
    asset = await _ready_asset(author.id)
    with patch("app.modules.posts.service.enqueue", AsyncMock()):
        return await author.post("/posts", json={"asset_ids": [asset]} | extra)


async def test_media_edit_is_saved_and_validated(make_user):
    author = await make_user()
    edit = {"filter": "mono", "brightness": 110, "contrast": 90, "saturate": 100}
    res = await _post(author, media_edits=[edit])
    assert res.json()["media"][0]["edit"] == edit
    assert (await _post(author, media_edits=[edit | {"filter": "url(evil)"}])).status_code == 422
    assert (await _post(author, media_edits=[edit | {"brightness": 500}])).status_code == 422


async def test_collab_shows_only_after_accepting(make_user, make_post):
    from app.core.database import SessionLocal
    from app.modules.posts.models import PostCollab

    author, partner, follower = await make_user(), await make_user(), await make_user()
    await _follow(follower, partner)
    made = await _post(author, draft=True, collab_username=partner.username)
    assert made.status_code == 201, made.text
    assert made.json()["collaborator"] is None
    refused = await _post(author, collab_username=author.username)
    assert refused.status_code == 400

    post_id = await make_post(author)
    async with SessionLocal() as s:
        s.add(PostCollab(post_id=uuid.UUID(post_id), user_id=uuid.UUID(partner.id)))
        await s.commit()
    requests = (await partner.get("/collab-requests")).json()
    assert post_id in [p["id"] for p in requests]
    assert (await follower.post(f"/posts/{post_id}/collab/accept")).status_code == 404

    with patch("app.modules.posts.service.emit", AsyncMock()):
        assert (await partner.post(f"/posts/{post_id}/collab/accept")).status_code == 204
    assert (await partner.get(f"/posts/{post_id}")).json()["collaborator"]["username"] == partner.username
    assert post_id in [p["id"] for p in (await follower.get(f"/users/{partner.username}/posts")).json()["items"]]
    assert post_id in [p["id"] for p in (await follower.get("/feed")).json()["items"]]
    assert (await partner.get("/collab-requests")).json() == []

    assert (await partner.delete(f"/posts/{post_id}/collab/me")).status_code == 204
    assert post_id not in [p["id"] for p in (await follower.get(f"/users/{partner.username}/posts")).json()["items"]]
    assert (await author.get(f"/posts/{post_id}")).json()["collaborator"] is None


async def test_blocked_person_cannot_be_invited(make_user):
    author, blocker = await make_user(), await make_user()
    await blocker.post(f"/users/{author.username}/block")
    assert (await _post(author, collab_username=blocker.username)).status_code == 400


async def test_pinning_limits_and_order(make_user, make_post):
    author, other = await make_user(), await make_user()
    ids = [await make_post(author) for _ in range(5)]
    for post_id in ids[:3]:
        assert (await author.post(f"/posts/{post_id}/pin")).status_code == 204
    assert (await author.post(f"/posts/{ids[3]}/pin")).status_code == 409
    assert (await other.post(f"/posts/{ids[3]}/pin")).status_code == 403

    items = (await other.get(f"/users/{author.username}/posts")).json()["items"]
    assert [p["id"] for p in items[:3]] == [ids[2], ids[1], ids[0]]
    assert [p["id"] for p in items[3:]] == [ids[4], ids[3]]
    assert all(p["pinned"] for p in items[:3]) and not items[3]["pinned"]
    assert len({p["id"] for p in items}) == 5

    assert (await author.delete(f"/posts/{ids[0]}/pin")).status_code == 204
    assert (await author.post(f"/posts/{ids[3]}/pin")).status_code == 204


async def test_pins_do_not_repeat_on_the_next_page(make_user, make_post):
    author = await make_user()
    ids = [await make_post(author) for _ in range(4)]
    await author.post(f"/posts/{ids[0]}/pin")
    first = (await author.get(f"/users/{author.username}/posts", params={"limit": 2})).json()
    second = (await author.get(f"/users/{author.username}/posts", params={"limit": 2, "cursor": first["next_cursor"]})).json()
    seen = [p["id"] for p in first["items"]] + [p["id"] for p in second["items"]]
    assert sorted(seen) == sorted(ids) and len(seen) == len(set(seen))


async def test_time_capsule_stays_sealed_until_its_date(make_user):
    from app.core.database import SessionLocal
    from app.modules.posts.models import Post

    author, other = await make_user(), await make_user()
    assert (await _post(author, is_capsule=True)).status_code == 400
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    assert (await _post(author, is_capsule=True, scheduled_at=past)).status_code == 400
    when = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    made = await _post(author, is_capsule=True, scheduled_at=when, caption="sealed words")
    assert made.status_code == 201, made.text
    post_id = made.json()["id"]
    assert made.json()["status"] == "scheduled" and made.json()["is_capsule"] is True

    assert (await other.get(f"/posts/{post_id}")).status_code == 404
    assert (await author.post(f"/posts/{post_id}/publish")).status_code == 409  # cannot be opened early
    teaser = (await other.get(f"/users/{author.username}/capsules")).json()
    assert teaser["count"] == 1 and teaser["next_unlock_at"]
    assert "sealed words" not in str(teaser)

    async with SessionLocal() as s:
        post = await s.get(Post, uuid.UUID(post_id))
        post.status, post.scheduled_at = "published", None
        await s.commit()
    from app.modules.posts import service

    await service.invalidate(uuid.UUID(post_id))
    opened = await other.get(f"/posts/{post_id}")
    assert opened.status_code == 200 and opened.json()["is_capsule"] is True
    assert (await other.get(f"/users/{author.username}/capsules")).json()["count"] == 0
