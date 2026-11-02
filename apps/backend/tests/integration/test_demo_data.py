"""The large demo set: correct totals, super admin control, and clean removal."""
import uuid

import pytest
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.modules.admin import demo_data, test_data
from app.modules.chat.models import ConversationMember, Message
from app.modules.comments.models import Comment
from app.modules.communities.models import CommunityMember
from app.modules.media.models import MediaAsset
from app.modules.notifications.models import Notification
from app.modules.posts.models import Hashtag, Like, Post
from app.modules.stories.models import Story
from app.modules.support.models import Ticket
from app.modules.users.models import User
from tests.integration.test_test_data import no_storage, set_role  # noqa: F401


@pytest.fixture
def small_demo(monkeypatch, no_storage):  # noqa: F811
    monkeypatch.setattr(demo_data, "DEMO_USERS", 6)
    monkeypatch.setattr(demo_data, "DEMO_POSTS", 40)
    monkeypatch.setattr(demo_data, "DEMO_REELS", 4)
    monkeypatch.setattr(demo_data, "DEMO_VIDEO_POSTS", 4)
    monkeypatch.setattr(demo_data, "DEMO_STORIES", 3)
    monkeypatch.setattr(demo_data, "FOLLOWS_EACH", 2)
    monkeypatch.setattr(demo_data, "MIN_PHOTOS", 2)
    monkeypatch.setattr(demo_data, "REAL_ACCOUNTS", ())
    monkeypatch.setattr(demo_data, "fetch_photos", lambda count: iter([b"a", b"b", b"c"]))
    monkeypatch.setattr(demo_data, "fetch_clips", lambda: [b"v"] * 8)
    monkeypatch.setattr(demo_data, "store_and_process", test_data.store_and_process)
    monkeypatch.setattr(demo_data, "enqueue", test_data.enqueue)
    return no_storage


async def _owner(make_user):
    owner = await make_user()
    await set_role(owner, "superadmin")
    return owner


async def _count(model, *where) -> int:
    async with SessionLocal() as s:
        return int((await s.execute(select(func.count()).select_from(model).where(*where))).scalar_one())


async def _create(owner) -> str:
    res = await owner.post("/admin/test-data/demo", json={"label": "Big demo"})
    assert res.status_code == 202, res.text
    batch_id = res.json()["id"]
    await test_data.create_batch(uuid.UUID(batch_id))
    return batch_id


async def _listed(owner, batch_id):
    return next(b for b in (await owner.get("/admin/test-data")).json() if b["id"] == batch_id)


async def test_demo_set_builds_correct_totals_then_removes_cleanly(make_user, make_post, small_demo):
    owner = await _owner(make_user)
    real = await make_user()
    real_post = await make_post(real, caption="my real post")
    batch_id = await _create(owner)
    batch = uuid.UUID(batch_id)

    listed = await _listed(owner, batch_id)
    assert listed["status"] == "ready" and listed["is_demo"] is True
    assert listed["user_count"] == 6 and listed["post_count"] == 40

    async with SessionLocal() as s:
        people = list((await s.execute(select(User).where(User.test_batch_id == batch))).scalars().unique())
        ids = [u.id for u in people]
        assert all(u.password_hash is None and u.email.endswith(".invalid") for u in people)
        assert sum(u.post_count for u in people) == 40
        assert sum(u.follower_count for u in people) == sum(u.following_count for u in people) == 12
        posts = list((await s.execute(select(Post).where(Post.author_id.in_(ids)))).scalars().unique())
        post_ids = [p.id for p in posts]
        assert sum(p.is_reel for p in posts) == 4
        assert all(p.media for p in posts)
        assert all(int(p.id.hex[:12], 16) == int(p.created_at.timestamp() * 1000) for p in posts)
        assert await _count(Like, Like.post_id.in_(post_ids)) == sum(p.like_count for p in posts)
        assert await _count(Comment, Comment.post_id.in_(post_ids)) == sum(p.comment_count for p in posts)
        tags_before = int((await s.execute(select(func.sum(Hashtag.post_count)))).scalar_one())

    assert await _count(Story, Story.author_id.in_(ids)) == 3
    shown = (await real.get(f"/posts/{post_ids[0]}")).json()  # backdated, so not always in the newest Explore page
    assert shown["author"]["id"] in {str(i) for i in ids} and shown["media"]

    assert (await owner.delete(f"/admin/test-data/{batch_id}")).status_code == 202
    await test_data.remove_batch(batch)

    assert await _count(User, User.test_batch_id == batch) == 0
    assert await _count(Post, Post.author_id.in_(ids)) == 0
    assert await _count(MediaAsset, MediaAsset.owner_id.in_(ids)) == 0
    assert await _count(Like, Like.post_id.in_(post_ids)) == 0
    assert (await real.get(f"/posts/{real_post}")).status_code == 200
    async with SessionLocal() as s:
        assert int((await s.execute(select(func.sum(Hashtag.post_count)))).scalar_one()) < tags_before
    assert (await _listed(owner, batch_id))["status"] == "removed"


async def test_only_super_admin_controls_the_demo_set(make_user, small_demo):
    owner = await _owner(make_user)
    admin = await make_user()
    await set_role(admin, "admin")
    assert (await admin.post("/admin/test-data/demo", json={})).status_code == 403

    batch_id = await _create(owner)
    assert (await owner.post("/admin/test-data/demo", json={})).status_code == 409  # one at a time
    assert (await admin.delete(f"/admin/test-data/{batch_id}")).status_code == 403
    assert (await admin.post("/admin/test-data/remove-all")).status_code == 202
    assert (await _listed(owner, batch_id))["status"] == "ready"  # an admin's remove all skips it

    assert (await owner.delete(f"/admin/test-data/{batch_id}")).status_code == 202
    await test_data.remove_batch(uuid.UUID(batch_id))


async def test_super_admin_disables_then_enables_then_removes(make_user, small_demo):
    owner = await _owner(make_user)
    admin = await make_user()
    await set_role(admin, "admin")
    viewer = await make_user()
    batch_id = await _create(owner)
    batch = uuid.UUID(batch_id)
    async with SessionLocal() as s:
        post_id = (await s.execute(
            select(Post.id).join(User, User.id == Post.author_id)
            .where(User.test_batch_id == batch, User.is_private.is_(False), Post.is_reel.is_(False)).limit(1)
        )).scalar_one()
    assert (await viewer.get(f"/posts/{post_id}")).status_code == 200

    assert (await admin.post(f"/admin/test-data/{batch_id}/disable")).status_code == 403
    assert (await owner.post(f"/admin/test-data/{batch_id}/enable")).status_code == 409  # it is not disabled yet
    assert (await owner.post(f"/admin/test-data/{batch_id}/disable")).status_code == 200
    assert (await _listed(owner, batch_id))["status"] == "disabled"
    assert (await viewer.get(f"/posts/{post_id}")).status_code == 404
    assert await _count(Post, Post.id == post_id) == 1  # hidden, not deleted

    assert (await owner.post(f"/admin/test-data/{batch_id}/enable")).status_code == 200
    assert (await _listed(owner, batch_id))["status"] == "ready"
    assert (await viewer.get(f"/posts/{post_id}")).status_code == 200

    assert (await owner.post(f"/admin/test-data/{batch_id}/disable")).status_code == 200
    assert (await owner.delete(f"/admin/test-data/{batch_id}")).status_code == 202  # a disabled set can still be deleted
    await test_data.remove_batch(batch)
    assert await _count(User, User.test_batch_id == batch) == 0


async def test_feature_data_reaches_real_accounts_and_removal_leaves_them_clean(make_user, small_demo, monkeypatch):
    owner = await _owner(make_user)
    real = await make_user()
    monkeypatch.setattr(demo_data, "REAL_ACCOUNTS", (real.username,))
    real_id = uuid.UUID(real.id)
    batch_id = await _create(owner)

    assert await _count(ConversationMember, ConversationMember.user_id == real_id) > 0
    assert await _count(Notification, Notification.user_id == real_id) == 30
    assert await _count(CommunityMember, CommunityMember.user_id == real_id) > 0
    assert await _count(Ticket, Ticket.subject == "Cannot upload my video") > 0
    assert (await real.get("/feed")).json()["items"]
    assert (await real.get("/conversations")).json()

    assert (await owner.delete(f"/admin/test-data/{batch_id}")).status_code == 202
    await test_data.remove_batch(uuid.UUID(batch_id))

    assert await _count(ConversationMember, ConversationMember.user_id == real_id) == 0
    assert await _count(Message, Message.sender_id == real_id) == 0
    assert await _count(Notification, Notification.user_id == real_id) == 0
    assert await _count(CommunityMember, CommunityMember.user_id == real_id) == 0
    async with SessionLocal() as s:
        left = await s.get(User, real_id)
        assert left.following_count == 0 and left.follower_count == 0


async def test_too_few_downloads_fail_visibly_and_stay_removable(make_user, small_demo, monkeypatch):
    monkeypatch.setattr(demo_data, "fetch_photos", lambda count: iter([]))
    owner = await _owner(make_user)
    batch_id = (await owner.post("/admin/test-data/demo", json={})).json()["id"]
    with pytest.raises(Exception):  # noqa: B017
        await test_data.create_batch(uuid.UUID(batch_id))
    assert (await _listed(owner, batch_id))["status"] == "failed"
    assert (await owner.delete(f"/admin/test-data/{batch_id}")).status_code == 202
    await test_data.remove_batch(uuid.UUID(batch_id))
    assert await _count(User, User.test_batch_id == uuid.UUID(batch_id)) == 0
