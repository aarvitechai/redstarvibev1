"""Search rules, AI off behaviour, indexing and the writing endpoints."""
import uuid
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.ai import writing
from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.posts.models import Post, PostMedia
from app.workers.ai_tasks import index_posts, pending_ids
from tests.integration.test_flows import OVERLAY, _ready_asset


def _word() -> str:
    return f"w{uuid.uuid4().hex[:10]}"


async def _indexed(make_post, author, caption, **kw) -> str:
    post_id = await make_post(author, caption=caption, **kw)
    await index_posts([uuid.UUID(post_id)])
    return post_id


async def _found(actor, q, kind="posts"):
    res = await actor.get("/search", params={"q": q, "type": kind})
    assert res.status_code == 200, res.text
    return res.json()["items"]


async def test_private_blocked_and_deleted_posts_never_appear(make_user, make_post, anon):
    word = _word()
    author, private, viewer, blocked_by, gone = [await make_user() for _ in range(5)]
    public = await _indexed(make_post, author, f"public {word}")
    hidden_author = await make_user(private=True)
    private_post = await _indexed(make_post, hidden_author, f"private {word}")
    followers = await _indexed(make_post, author, f"followers {word}", visibility="followers")
    draft = await _indexed(make_post, author, f"draft {word}", status="draft")
    blocked_post = await _indexed(make_post, blocked_by, f"blocked {word}")
    await blocked_by.post(f"/users/{viewer.username}/block")
    deleted = await _indexed(make_post, gone, f"deleted {word}")
    with patch("app.modules.posts.service.emit", AsyncMock()):
        await gone.delete(f"/posts/{deleted}")

    seen = [p["id"] for p in await _found(viewer, word)]
    assert public in seen
    for hidden in (private_post, followers, draft, blocked_post, deleted):
        assert hidden not in seen
    public_seen = [p["id"] for p in (await anon.get("/api/v1/search", params={"q": word})).json()["items"]]
    assert public in public_seen and private_post not in public_seen and followers not in public_seen

    await viewer.post(f"/users/{hidden_author.username}/follow")
    await hidden_author.post(f"/follow-requests/{viewer.id}/accept")
    assert private_post in [p["id"] for p in await _found(viewer, word)]


async def test_shared_cache_never_serves_a_private_post(make_user, make_post, anon):
    word = _word()
    author = await make_user(private=True)
    follower = await make_user()
    await follower.post(f"/users/{author.username}/follow")
    await author.post(f"/follow-requests/{follower.id}/accept")
    post_id = await _indexed(make_post, author, f"secret {word}")
    assert post_id in [p["id"] for p in await _found(follower, word)]  # logged in first
    assert (await anon.get("/api/v1/search", params={"q": word})).json()["items"] == []
    assert post_id in [p["id"] for p in await _found(follower, word)]


async def test_search_works_with_ai_off(make_user, make_post):
    assert settings.ai_provider == "none"
    word = _word()
    a = await make_user()
    post_id = await _indexed(make_post, a, f"{word} at sunset")
    assert post_id in [p["id"] for p in await _found(a, word)]
    assert post_id in [p["id"] for p in await _found(a, f"#{word.upper()}")]  # normalized
    assert (await a.get(f"/posts/{post_id}/similar")).json() == []
    assert (await a.get("/ai/features")).json() == {"semantic_search": False, "writing": False, "captions": False}


async def test_search_survives_a_model_that_is_down(make_user, make_post):
    word = _word()
    a = await make_user()
    post_id = await _indexed(make_post, a, f"{word} beach")
    with patch.object(settings, "ai_provider", "cloudflare"), patch("app.ai.workers_ai.embed", AsyncMock(return_value=None)):
        assert post_id in [p["id"] for p in await _found(a, word)]


async def test_typos_are_forgiven(make_user, make_post):
    word = f"zxqmonsoonvibes{uuid.uuid4().hex[:6]}"
    a = await make_user()
    post_id = await _indexed(make_post, a, f"{word} today")
    assert post_id in [p["id"] for p in await _found(a, word[:-1] + "!")]
    people = await _found(a, a.username[:-1] + "x", "users")
    assert a.username in [u["username"] for u in people]


async def test_index_task_reads_text_on_media_too(make_user):
    word = _word()
    a = await make_user()
    asset = await _ready_asset(a.id)
    async with SessionLocal() as s:
        post = Post(author_id=uuid.UUID(a.id), caption="plain caption", status="published", location="Hampi")
        post.media = [PostMedia(asset_id=uuid.UUID(asset), position=0, text_overlay=OVERLAY | {"text": f"overlay {word}"})]
        s.add(post)
        await s.commit()
        post_id = post.id
    await index_posts([post_id])
    assert str(post_id) in [p["id"] for p in await _found(a, word)]
    async with SessionLocal() as s:
        row = (await s.execute(select(Post.search_text, Post.indexed_at).where(Post.id == post_id))).one()
    assert "Hampi" in row[0] and word in row[0] and row[1] is not None


async def test_vectors_are_stored_and_similar_posts_respect_privacy(make_user, make_post):
    a, b, viewer = await make_user(), await make_user(private=True), await make_user()
    vector = [0.0] * 1024
    vector[0] = 1.0
    with patch.object(settings, "ai_provider", "cloudflare"), patch("app.ai.workers_ai.embed", AsyncMock(return_value=[vector])):
        first = await _indexed(make_post, a, "one")
        second = await _indexed(make_post, a, "two")
        private = await _indexed(make_post, b, "three")
    async with SessionLocal() as s:
        model = (await s.execute(select(Post.embedding_model).where(Post.id == uuid.UUID(first)))).scalar_one()
    assert model == settings.embed_model
    similar = [p["id"] for p in (await viewer.get(f"/posts/{first}/similar")).json()]
    assert second in similar and first not in similar and private not in similar
    assert (await viewer.get(f"/posts/{private}/similar")).status_code == 404


async def test_backfill_finds_new_posts_and_model_changes(make_user, make_post):
    a = await make_user()
    post_id = uuid.UUID(await make_post(a))
    assert post_id in await pending_ids(5000)
    await index_posts([post_id])
    assert post_id not in await pending_ids(5000)
    with patch.object(settings, "ai_provider", "cloudflare"):
        assert post_id in await pending_ids(5000)  # indexed, but with no vector from the current model


async def test_suggest_and_tags(make_user, make_post):
    from app.modules.posts import repository as repo

    a = await make_user()
    tag = f"tg{uuid.uuid4().hex[:8]}"
    post = await make_post(a, caption=f"hello #{tag}")
    async with SessionLocal() as s:
        await repo.link_hashtags(s, uuid.UUID(post), [tag])
        await s.commit()
    data = (await a.get("/search/suggest", params={"q": tag})).json()
    assert [t["tag"] for t in data["tags"]] == [tag]
    assert a.username in [u["username"] for u in (await a.get("/search/suggest", params={"q": a.username})).json()["users"]]
    assert (await a.get("/search", params={"q": "x", "cursor": "bad!"})).status_code == 400


async def test_composer_endpoints_say_disabled_when_ai_is_off(make_user):
    a, other = await make_user(), await make_user()
    asset = await _ready_asset(a.id)
    assert (await a.get(f"/ai/captions/{asset}")).json()["status"] == "disabled"
    assert (await other.get(f"/ai/captions/{asset}")).status_code == 404
    assert (await a.post("/ai/rewrite", json={"text": "hi", "style": "fun"})).json() == {"status": "disabled", "text": None}
    assert (await a.post("/ai/hashtags", json={"text": "hi"})).json()["status"] == "disabled"
    assert (await a.post("/ai/rewrite", json={"text": "hi", "style": "evil"})).status_code == 422


async def test_rewrite_is_rate_limited_and_reports_failure(make_user):
    a = await make_user()
    with patch.object(settings, "ai_provider", "cloudflare"):
        with patch("app.ai.workers_ai.chat", AsyncMock(return_value='"new words"')):
            assert (await a.post("/ai/rewrite", json={"text": "hi", "style": "short"})).json()["text"] == "new words"
        with patch("app.ai.workers_ai.chat", AsyncMock(return_value=None)):
            assert (await a.post("/ai/rewrite", json={"text": "hi", "style": "short"})).json()["status"] == "failed"
            for _ in range(18):
                await a.post("/ai/rewrite", json={"text": "hi", "style": "short"})
            assert (await a.post("/ai/rewrite", json={"text": "hi", "style": "short"})).status_code == 429


async def test_caption_flow_stores_suggestions_for_the_owner(make_user):
    from app.modules.assistant.suggestions import store_captions

    a = await make_user()
    asset = await _ready_asset(a.id)
    with patch.object(settings, "ai_provider", "cloudflare"):
        assert (await a.get(f"/ai/captions/{asset}")).json()["status"] == "pending"
        await store_captions(uuid.UUID(asset), {"captions": ["One"], "tagline": "Go", "hashtags": ["a"]})
        data = (await a.get(f"/ai/captions/{asset}")).json()
        expected = {"status": "ready", "captions": ["One"], "tagline": "Go", "hashtags": ["a"], "alt_text": None, "music": None}
        assert data == expected
        await store_captions(uuid.UUID(asset), None)
        assert (await a.get(f"/ai/captions/{asset}")).json()["status"] == "failed"


async def test_bad_model_output_gets_one_retry_then_gives_up():
    good = '{"captions": ["Nice"], "tagline": "Wow", "hashtags": ["x"]}'
    with patch.object(settings, "ai_provider", "cloudflare"):
        chat = AsyncMock(side_effect=["not json", good])
        with patch("app.ai.workers_ai.chat", chat):
            assert (await writing.suggest_from_image(b"x"))["captions"] == ["Nice"]
        chat = AsyncMock(return_value="still not json")
        with patch("app.ai.workers_ai.chat", chat):
            assert await writing.suggest_from_image(b"x") is None
        assert chat.await_count == 2
        chat = AsyncMock(return_value=good)
        with patch("app.ai.workers_ai.chat", chat):
            await writing.suggest_from_image(b"x", is_video=True)
        assert chat.await_args.args[2] == writing.VIDEO_PROMPT
