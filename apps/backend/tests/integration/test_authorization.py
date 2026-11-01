"""Definition of Done: authorization checks tested, including other user's object (IDOR)."""


async def test_private_account_post_hidden_until_follow_accepted(make_user, make_post, anon):
    owner = await make_user(private=True)
    other = await make_user()
    post = await make_post(owner)
    assert (await other.get(f"/posts/{post}")).status_code == 404
    assert (await anon.get(f"/api/v1/posts/{post}")).status_code == 404
    assert (await other.get(f"/users/{owner.username}/posts")).status_code == 403

    res = await other.post(f"/users/{owner.username}/follow")
    assert res.json()["status"] == "pending"
    assert (await other.get(f"/posts/{post}")).status_code == 404
    assert (await owner.post(f"/follow-requests/{other.id}/accept")).status_code == 204
    assert (await other.get(f"/posts/{post}")).status_code == 200


async def test_followers_only_post(make_user, make_post):
    owner, follower, stranger = await make_user(), await make_user(), await make_user()
    post = await make_post(owner, visibility="followers")
    await follower.post(f"/users/{owner.username}/follow")
    assert (await follower.get(f"/posts/{post}")).status_code == 200
    assert (await stranger.get(f"/posts/{post}")).status_code == 404


async def test_block_hides_both_ways_and_removes_follows(make_user, make_post):
    a, b = await make_user(), await make_user()
    post = await make_post(a)
    await b.post(f"/users/{a.username}/follow")
    assert (await a.post(f"/users/{b.username}/block")).status_code == 204
    assert (await b.get(f"/posts/{post}")).status_code == 404
    assert (await b.get(f"/users/{a.username}")).status_code == 404
    assert (await b.post(f"/posts/{post}/like")).status_code == 404
    assert (await b.post(f"/users/{a.username}/follow")).status_code == 404
    assert (await a.get(f"/users/{a.username}")).json()["follower_count"] == 0


async def test_cannot_edit_or_delete_others_post(make_user, make_post):
    owner, other = await make_user(), await make_user()
    post = await make_post(owner)
    assert (await other.patch(f"/posts/{post}", json={"caption": "hacked"})).status_code == 403
    assert (await other.delete(f"/posts/{post}")).status_code == 403
    assert (await other.get(f"/posts/{post}/insights")).status_code == 403


async def test_draft_is_only_visible_to_owner(make_user, make_post):
    owner, other = await make_user(), await make_user()
    post = await make_post(owner, status="draft")
    assert (await owner.get(f"/posts/{post}")).status_code == 200
    assert (await other.get(f"/posts/{post}")).status_code == 404


async def test_comment_delete_rules(make_user, make_post):
    owner, commenter, other = await make_user(), await make_user(), await make_user()
    post = await make_post(owner)
    c1 = (await commenter.post(f"/posts/{post}/comments", json={"body": "nice"})).json()["id"]
    assert (await other.delete(f"/comments/{c1}")).status_code == 403
    assert (await owner.delete(f"/comments/{c1}")).status_code == 204  # the post owner may moderate


async def test_conversation_not_visible_to_non_member(make_user):
    a, b, c = await make_user(), await make_user(), await make_user()
    conv = (await a.post("/conversations", json={"usernames": [b.username]})).json()["id"]
    assert (await c.get(f"/conversations/{conv}")).status_code == 404
    assert (await c.get(f"/conversations/{conv}/messages")).status_code == 404
    assert (await c.post(f"/conversations/{conv}/messages", json={"body": "hi"})).status_code == 404
    assert (await b.post(f"/conversations/{conv}/messages", json={"body": "hi"})).status_code == 201


async def test_call_token_only_for_members(make_user):
    a, b, c = await make_user(), await make_user(), await make_user()
    conv = (await a.post("/conversations", json={"usernames": [b.username]})).json()["id"]
    assert (await c.post("/calls", json={"conversation_id": conv, "kind": "video"})).status_code == 404
    call = (await a.post("/calls", json={"conversation_id": conv, "kind": "video"})).json()
    assert call["token"]
    assert (await b.post(f"/calls/rooms/{call['room']}/join")).status_code == 200
    assert (await c.post(f"/calls/rooms/{call['room']}/join")).status_code == 404


async def test_media_upload_belongs_to_owner(make_user):
    a, b = await make_user(), await make_user()
    res = await a.post("/media/uploads", json={
        "filename": "a.jpg", "content_type": "image/jpeg", "size": 100, "purpose": "post",
    })
    assert res.status_code == 201
    asset = res.json()["asset_id"]
    assert (await b.get(f"/media/{asset}")).status_code == 404
    assert (await b.post("/posts", json={"asset_ids": [asset]})).status_code == 400


async def test_upload_validation(make_user):
    a = await make_user()
    bad_type = await a.post("/media/uploads", json={
        "filename": "x.exe", "content_type": "application/x-msdownload", "size": 100, "purpose": "post",
    })
    assert bad_type.status_code == 400
    too_big = await a.post("/media/uploads", json={
        "filename": "x.jpg", "content_type": "image/jpeg", "size": 21 * 1024 * 1024, "purpose": "post",
    })
    assert too_big.json()["error"]["code"] == "file_too_large"


async def test_admin_requires_role(make_user):
    a = await make_user()
    assert (await a.get("/admin/stats")).status_code == 403


async def test_assistant_only_retrieves_own_private_content(make_user):
    import uuid

    from app.ai.rag.ingest import upsert_entity
    from app.ai.rag.retriever import retrieve
    from app.core.database import SessionLocal

    a, b = await make_user(), await make_user()
    secret = "zebraquartz private plan for the surprise party"
    async with SessionLocal() as s:
        await upsert_entity(s, "own_post", str(uuid.uuid4()), uuid.UUID(a.id), "Your post", secret)
        await s.commit()
        mine = await retrieve(s, uuid.UUID(a.id), "zebraquartz surprise party")
        theirs = await retrieve(s, uuid.UUID(b.id), "zebraquartz surprise party")
    assert any("zebraquartz" in c.text for c in mine)
    assert not any("zebraquartz" in c.text for c in theirs)
