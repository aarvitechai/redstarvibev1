import uuid
from unittest.mock import AsyncMock, patch


async def test_like_is_idempotent_and_counted(make_user, make_post):
    a, b = await make_user(), await make_user()
    post = await make_post(a)
    assert (await b.post(f"/posts/{post}/like")).json() == {"liked": True, "like_count": 1}
    assert (await b.post(f"/posts/{post}/like")).json()["like_count"] == 1
    assert (await b.get(f"/posts/{post}")).json()["liked"] is True
    assert (await b.delete(f"/posts/{post}/like")).json() == {"liked": False, "like_count": 0}


async def test_counters_flush_to_postgres(make_user, make_post):
    from app.core.database import SessionLocal
    from app.modules.posts.models import Post
    from app.workers.feed_tasks import _flush

    a, b = await make_user(), await make_user()
    post = await make_post(a)
    await b.post(f"/posts/{post}/like")
    await _flush()
    async with SessionLocal() as s:
        row = await s.get(Post, uuid.UUID(post))
        assert row.like_count == 1
    assert (await a.get(f"/posts/{post}")).json()["like_count"] == 1  # no double count after flush


async def test_comments_and_replies_nest_one_level(make_user, make_post):
    a, b = await make_user(), await make_user()
    post = await make_post(a)
    top = (await b.post(f"/posts/{post}/comments", json={"body": "first"})).json()
    reply = (await a.post(f"/posts/{post}/comments", json={"body": "r1", "parent_id": top["id"]})).json()
    nested = (await b.post(f"/posts/{post}/comments", json={"body": "r2", "parent_id": reply["id"]})).json()
    assert nested["parent_id"] == top["id"]
    listing = (await a.get(f"/posts/{post}/comments")).json()["items"]
    assert [c["id"] for c in listing] == [top["id"]] and listing[0]["reply_count"] == 2


async def test_feed_shows_followed_posts_with_cursor(make_user, make_post):
    a, b = await make_user(), await make_user()
    await b.post(f"/users/{a.username}/follow")
    ids = [await make_post(a, f"p{i}") for i in range(3)]
    from app.modules.feed.service import invalidate_feed

    await invalidate_feed(uuid.UUID(b.id))
    first = (await b.get("/feed", params={"limit": 2})).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    second = (await b.get("/feed", params={"limit": 2, "cursor": first["next_cursor"]})).json()
    got = {p["id"] for p in first["items"]} | {p["id"] for p in second["items"]}
    assert got == set(ids)


async def test_fan_out_reaches_built_feeds_only(make_user, make_post):
    from app.core.cache import get_redis
    from app.modules.feed.service import fan_out, feed_key

    a, b, c = await make_user(), await make_user(), await make_user()
    await b.post(f"/users/{a.username}/follow")
    await b.get("/feed")  # builds b's feed
    post = await make_post(a)
    await fan_out(uuid.UUID(post), [uuid.UUID(b.id), uuid.UUID(c.id)])
    assert post in [p["id"] for p in (await b.get("/feed")).json()["items"]]
    assert not await get_redis().exists(feed_key(uuid.UUID(c.id)))


async def test_idempotent_post_create(make_user):
    from app.core.database import SessionLocal
    from app.modules.media.models import MediaAsset

    a = await make_user()
    async with SessionLocal() as s:
        asset = MediaAsset(
            owner_id=uuid.UUID(a.id), purpose="post", kind="image", raw_key="k", declared_type="image/jpeg",
            size_bytes=1, status="ready", variants={"images": []},
        )
        s.add(asset)
        await s.commit()
        aid = str(asset.id)
    key = {"Idempotency-Key": uuid.uuid4().hex}
    one = await a.post("/posts", json={"asset_ids": [aid], "draft": True}, headers=key)
    two = await a.post("/posts", json={"asset_ids": [aid], "draft": True}, headers=key)
    assert one.status_code == 201 and two.json()["id"] == one.json()["id"]


async def _ready_asset(owner_id: str) -> str:
    import uuid

    from app.core.database import SessionLocal
    from app.modules.media.models import MediaAsset

    async with SessionLocal() as s:
        asset = MediaAsset(
            owner_id=uuid.UUID(owner_id), purpose="post", kind="image", raw_key=f"{owner_id}/x", declared_type="image/jpeg",
            size_bytes=1, status="ready", width=10, height=10, variants={"images": [{"w": 10, "webp": "x.webp"}]},
        )
        s.add(asset)
        await s.commit()
        return str(asset.id)


OVERLAY = {"text": "  Big sale today  ", "x": 50, "y": 15, "size": "large", "style": "highlight", "color": "#C8102E"}


async def test_text_on_media_is_saved_and_returned(make_user):
    a = await make_user()
    with patch("app.modules.posts.service.enqueue", AsyncMock()):
        res = await a.post("/posts", json={"asset_ids": [await _ready_asset(a.id)], "caption": "hi", "text_overlays": [OVERLAY]})
    assert res.status_code == 201, res.text
    saved = res.json()["media"][0]["text_overlay"]
    assert saved["text"] == "Big sale today"
    assert saved["y"] == 15
    fetched = await a.get(f"/posts/{res.json()['id']}")
    assert fetched.json()["media"][0]["text_overlay"]["style"] == "highlight"


async def test_bad_text_on_media_is_rejected(make_user):
    a = await make_user()
    asset = await _ready_asset(a.id)
    for bad in ({"color": "red;"}, {"x": 101}, {"style": "html"}, {"text": "   "}, {"text": "x" * 201}):
        res = await a.post("/posts", json={"asset_ids": [asset], "text_overlays": [OVERLAY | bad]})
        assert res.status_code == 422, bad


def test_moderation_reads_text_on_media():
    from app.modules.posts.models import Post, PostMedia

    post = Post(caption="nice photo")
    post.media = [PostMedia(text_overlay=OVERLAY | {"text": "words on the photo"}), PostMedia()]
    assert "words on the photo" in post.full_text
    assert "nice photo" in post.full_text


async def test_search_finds_users_and_tags(make_user, make_post):
    from app.core.database import SessionLocal
    from app.modules.posts import repository as repo

    a = await make_user()
    post = await make_post(a, "lovely #uniquetagx")
    async with SessionLocal() as s:
        await repo.link_hashtags(s, uuid.UUID(post), ["uniquetagx"])
        await s.commit()
    res = (await a.get("/search", params={"q": a.username})).json()
    assert a.username in [u["username"] for u in res["users"]]
    assert "uniquetagx" in [h["tag"] for h in (await a.get("/search", params={"q": "uniquetag"})).json()["hashtags"]]
    assert post in [p["id"] for p in (await a.get("/hashtags/uniquetagx/posts")).json()["items"]]


async def test_notifications_created_and_marked_read(make_user, make_post):
    from app.core.database import SessionLocal
    from app.modules.notifications.service import notify

    a, b = await make_user(), await make_user()
    async with SessionLocal() as s:
        await notify(s, uuid.UUID(a.id), "follow", uuid.UUID(b.id))
    assert (await a.get("/notifications/unread-count")).json()["count"] == 1
    assert (await a.get("/notifications")).json()["items"][0]["actor"]["username"] == b.username
    await a.post("/notifications/read")
    assert (await a.get("/notifications/unread-count")).json()["count"] == 0


async def test_message_seen_flow(make_user):
    a, b = await make_user(), await make_user()
    await b.post(f"/users/{a.username}/follow")
    conv = (await a.post("/conversations", json={"usernames": [b.username]})).json()["id"]
    same = (await b.post("/conversations", json={"usernames": [a.username]})).json()["id"]
    assert conv == same  # one 1:1 per pair
    await a.post(f"/conversations/{conv}/messages", json={"body": "hello"})
    listed = (await b.get("/conversations")).json()
    assert listed[0]["unread"] == 1 and listed[0]["last_message"]["body"] == "hello"
    await b.post(f"/conversations/{conv}/seen")
    assert (await b.get("/conversations")).json()[0]["unread"] == 0


async def test_data_export_and_deletion(make_user, make_post):
    a = await make_user()
    await make_post(a, "my data")
    export = (await a.get("/users/me/export")).json()
    assert export["posts"][0]["caption"] == "my data"
    assert (await a.delete("/users/me")).status_code == 204
    me = (await a.get("/auth/me")).json()
    assert me["status"] == "deleting" and me["delete_after"]
    assert (await a.post("/users/me/restore")).status_code == 204


async def test_assistant_answers_without_llm(make_user):
    from app.ai.rag.ingest import ingest_help_docs
    from app.core.database import SessionLocal

    a = await make_user()
    async with SessionLocal() as s:
        await ingest_help_docs(s)
    res = (await a.post("/ai/assistant", json={"question": "How long do stories last?"})).json()
    assert "24" in res["answer"] and res["citations"]


def test_mcp_token_round_trip_and_audience():
    import jwt
    import pytest

    from app.core.security import create_access_token, create_mcp_token, decode_token

    uid = uuid.uuid4()
    assert decode_token(create_mcp_token(uid, ["read"], "c"), typ="mcp")["sub"] == str(uid)
    with pytest.raises(jwt.InvalidTokenError):  # an MCP token is not a session
        decode_token(create_mcp_token(uid, ["read"], "c"))
    with pytest.raises(jwt.InvalidTokenError):  # a session is not an MCP token
        decode_token(create_access_token(uid)[0], typ="mcp")


async def test_mcp_token_rejected_on_rest_and_oauth_pkce(make_user):
    import base64
    import hashlib

    a = await make_user()
    client = (await a.c.post("/api/v1/oauth/register", json={"redirect_uris": ["http://localhost:9999/cb"]})).json()
    verifier = "v" * 50
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    consent = await a.post("/oauth/consent", json={
        "client_id": client["client_id"], "redirect_uri": "http://localhost:9999/cb", "code_challenge": challenge,
        "state": "s", "scope": "read", "approve": True,
    })
    code = consent.json()["redirect_to"].split("code=")[1].split("&")[0]
    wrong = await a.c.post("/api/v1/oauth/token", data={
        "grant_type": "authorization_code", "client_id": client["client_id"], "code": code,
        "redirect_uri": "http://localhost:9999/cb", "code_verifier": "x" * 50,
    })
    assert wrong.status_code == 400
    # The code is single use, so a failed exchange burns it.
    again = await a.c.post("/api/v1/oauth/token", data={
        "grant_type": "authorization_code", "client_id": client["client_id"], "code": code,
        "redirect_uri": "http://localhost:9999/cb", "code_verifier": verifier,
    })
    assert again.status_code == 400


async def test_purge_removes_a_user_who_has_conversations_and_likes(make_user, make_post):
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.modules.chat.models import Message
    from app.modules.posts.models import Like
    from app.modules.users.models import User
    from app.workers.feed_tasks import _purge_accounts

    a, b = await make_user(), await make_user()
    post = await make_post(b)
    await make_post(a, "my own post with media")
    conv = (await a.post("/conversations", json={"usernames": [b.username]})).json()["id"]
    await a.post(f"/conversations/{conv}/messages", json={"body": "bye"})
    await a.post(f"/posts/{post}/like")
    await a.delete("/users/me")
    async with SessionLocal() as s:
        user = await s.get(User, uuid.UUID(a.id))
        user.delete_after = user.created_at
        await s.commit()
    await _purge_accounts()
    async with SessionLocal() as s:
        assert await s.get(User, uuid.UUID(a.id)) is None
        assert not (await s.execute(select(Like).where(Like.user_id == uuid.UUID(a.id)))).first()
        assert not (await s.execute(select(Message).where(Message.sender_id == uuid.UUID(a.id)))).first()
