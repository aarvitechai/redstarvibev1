"""Password reset, mute, restrict, hidden words, post tags and hashtag sorting."""
import uuid
from unittest.mock import AsyncMock, patch

from tests.conftest import PASSWORD

NEW_PASSWORD = "another long passphrase 42"


async def test_password_reset_changes_password_and_ends_sessions(make_user, anon):
    a = await make_user()
    email = f"{a.username}@example.com"
    sent = AsyncMock()
    with patch("app.modules.auth.service.enqueue", sent):
        assert (await anon.post("/api/v1/auth/password/forgot", json={"email": email})).status_code == 202
    code = sent.call_args_list[0].args[3].split("code is ")[1][:6]

    wrong = await anon.post("/api/v1/auth/password/reset", json={"email": email, "code": "000000", "password": NEW_PASSWORD})
    assert wrong.status_code == 400
    with patch("app.modules.auth.service.enqueue", AsyncMock()):
        ok = await anon.post("/api/v1/auth/password/reset", json={"email": email, "code": code, "password": NEW_PASSWORD})
    assert ok.status_code == 204, ok.text

    assert (await a.get("/auth/me")).status_code == 401  # the old session is over
    assert (await anon.post("/api/v1/auth/login", json={"identifier": a.username, "password": PASSWORD})).status_code == 401
    assert (await anon.post("/api/v1/auth/login", json={"identifier": a.username, "password": NEW_PASSWORD})).status_code == 200


async def test_forgot_password_does_not_reveal_accounts(anon):
    sent = AsyncMock()
    with patch("app.modules.auth.service.enqueue", sent):
        res = await anon.post("/api/v1/auth/password/forgot", json={"email": f"{uuid.uuid4().hex}@example.com"})
    assert res.status_code == 202
    sent.assert_not_called()


async def test_mute_hides_from_feed_but_keeps_the_follow(make_user, make_post):
    me, other = await make_user(), await make_user()
    await me.post(f"/users/{other.username}/follow")
    post_id = await make_post(other)
    assert post_id in [p["id"] for p in (await me.get("/feed")).json()["items"]]

    assert (await me.post(f"/users/{other.username}/mute")).status_code == 204
    assert post_id not in [p["id"] for p in (await me.get("/feed")).json()["items"]]
    profile = (await me.get(f"/users/{other.username}")).json()
    assert profile["is_muted"] is True and profile["follow_status"] == "active"
    assert (await other.get(f"/users/{me.username}")).json()["is_muted"] is False  # the other person cannot tell

    assert (await me.delete(f"/users/{other.username}/mute")).status_code == 204
    assert post_id in [p["id"] for p in (await me.get("/feed")).json()["items"]]


async def test_restricted_comment_is_visible_only_to_its_author_and_the_post_owner(make_user, make_post):
    owner, rude, third = await make_user(), await make_user(), await make_user()
    post_id = await make_post(owner)
    await owner.post(f"/users/{rude.username}/restrict")
    emit = AsyncMock()
    with patch("app.modules.comments.service.emit", emit):
        res = await rude.post(f"/posts/{post_id}/comments", json={"body": "you again"})
    assert res.json()["held"] is True
    emit.assert_not_called()  # no notification

    bodies = lambda r: [c["body"] for c in r.json()["items"]]  # noqa: E731
    assert bodies(await rude.get(f"/posts/{post_id}/comments")) == ["you again"]
    assert bodies(await owner.get(f"/posts/{post_id}/comments")) == ["you again"]
    assert bodies(await third.get(f"/posts/{post_id}/comments")) == []
    assert (await third.get(f"/posts/{post_id}")).json()["comment_count"] == 0

    assert (await third.post(f"/comments/{res.json()['id']}/approve")).status_code == 403
    assert (await owner.post(f"/comments/{res.json()['id']}/approve")).status_code == 204
    assert bodies(await third.get(f"/posts/{post_id}/comments")) == ["you again"]
    assert (await third.get(f"/posts/{post_id}")).json()["comment_count"] == 1


async def test_hidden_words_hold_whole_words_only(make_user, make_post):
    owner, other = await make_user(), await make_user()
    post_id = await make_post(owner)
    res = await owner.patch("/users/me", json={"hidden_words": ["  SPAM ", "spam", "", "buy now"]})
    assert res.json()["hidden_words"] == ["buy now", "spam"]

    async def held(body):
        return (await other.post(f"/posts/{post_id}/comments", json={"body": body})).json()["held"]

    assert await held("this is Spam!") is True
    assert await held("please BUY NOW") is True
    assert await held("spamming is a different word") is False
    own = await owner.post(f"/posts/{post_id}/comments", json={"body": "my own spam"})
    assert own.json()["held"] is False


async def test_tagging_people_in_a_post(make_user):
    from tests.integration.test_flows import _ready_asset

    a, b, blocker = await make_user(), await make_user(), await make_user()
    await blocker.post(f"/users/{a.username}/block")
    asset = await _ready_asset(a.id)
    with patch("app.modules.posts.service.enqueue", AsyncMock()):
        refused = await a.post("/posts", json={"asset_ids": [asset], "tagged_usernames": [blocker.username]})
        assert refused.status_code == 400
        res = await a.post("/posts", json={"asset_ids": [asset], "tagged_usernames": [b.username, b.username]})
    assert res.status_code == 201, res.text
    post_id = res.json()["id"]
    assert [u["username"] for u in res.json()["tagged"]] == [b.username]

    assert (await a.delete(f"/posts/{post_id}/tags/me")).status_code == 404
    assert (await b.delete(f"/posts/{post_id}/tags/me")).status_code == 204
    assert (await a.get(f"/posts/{post_id}")).json()["tagged"] == []


async def test_tagged_tab_respects_post_visibility(make_user, make_post):
    from app.core.database import SessionLocal
    from app.modules.posts.models import PostTag

    author, tagged, viewer = await make_user(private=True), await make_user(), await make_user()
    post_id = await make_post(author)
    async with SessionLocal() as s:
        s.add(PostTag(post_id=uuid.UUID(post_id), user_id=uuid.UUID(tagged.id)))
        await s.commit()
    assert (await viewer.get(f"/users/{tagged.username}/tagged")).json()["items"] == []
    await author.get(f"/posts/{post_id}")
    await viewer.post(f"/users/{author.username}/follow")
    await author.post(f"/follow-requests/{viewer.id}/accept")
    assert [p["id"] for p in (await viewer.get(f"/users/{tagged.username}/tagged")).json()["items"]] == [post_id]


async def test_hashtag_top_and_recent(make_user, make_post):
    from app.core.database import SessionLocal
    from app.modules.posts.models import Hashtag, Post, PostHashtag

    a = await make_user()
    tag = f"t{uuid.uuid4().hex[:10]}"
    ids = [await make_post(a) for _ in range(3)]
    async with SessionLocal() as s:
        s.add(Hashtag(tag=tag, post_count=3))
        await s.flush()
        for post_id, likes in zip(ids, (9, 1, 5), strict=True):
            s.add(PostHashtag(tag=tag, post_id=uuid.UUID(post_id)))
            (await s.get(Post, uuid.UUID(post_id))).like_count = likes
        await s.commit()

    recent = (await a.get(f"/hashtags/{tag}/posts")).json()
    assert [p["id"] for p in recent["items"]] == list(reversed(ids))

    first = (await a.get(f"/hashtags/{tag}/posts", params={"sort": "top", "limit": 2})).json()
    assert [p["id"] for p in first["items"]] == [ids[0], ids[2]]
    second = (await a.get(f"/hashtags/{tag}/posts", params={"sort": "top", "limit": 2, "cursor": first["next_cursor"]})).json()
    assert [p["id"] for p in second["items"]] == [ids[1]]
    assert second["next_cursor"] is None
