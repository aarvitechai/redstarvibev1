"""Removal must delete exactly what the batch created, and leave real people's data and counts correct."""
import uuid

import pytest
from sqlalchemy import select, update

from app.core.database import SessionLocal
from app.modules.admin import test_data
from app.modules.admin.models import TestDataBatch
from app.modules.media.models import MediaAsset
from app.modules.posts.models import Hashtag, Post
from app.modules.users.models import User


async def set_role(actor, role):
    async with SessionLocal() as s:
        await s.execute(update(User).where(User.id == uuid.UUID(actor.id)).values(role=role))
        await s.commit()


@pytest.fixture
def no_storage(monkeypatch):
    async def fake(s, owner, purpose, data, kind="image"):
        asset = MediaAsset(
            owner_id=owner, purpose=purpose, kind=kind, raw_key=f"{owner}/{uuid.uuid4()}", declared_type="image/jpeg",
            size_bytes=1, status="ready", width=10, height=10,
            variants={"images": [{"w": 10, "webp": "x.webp", "avif": "x.avif"}]},
        )
        s.add(asset)
        await s.commit()
        return asset

    queued = []

    async def fake_enqueue(task, *args, queue="default"):
        queued.append((task, args))

    monkeypatch.setattr(test_data, "store_and_process", fake)
    monkeypatch.setattr(test_data, "make_test_clip", lambda: b"")
    monkeypatch.setattr("app.workers.feed_tasks.delete_stored_media", lambda *a: None)
    monkeypatch.setattr(test_data, "enqueue", fake_enqueue)
    return queued


PAYLOAD = {"label": "t", "users": 3, "posts_per_user": 1, "reels": 1, "stories": 1}


async def make_batch(admin) -> str:
    res = await admin.post("/admin/test-data", json=PAYLOAD)
    assert res.status_code == 202, res.text
    batch_id = res.json()["id"]
    await test_data.create_batch(uuid.UUID(batch_id))
    return batch_id


async def test_only_admins_can_manage_test_data(make_user, no_storage):
    user = await make_user()
    assert (await user.get("/admin/test-data")).status_code == 403
    assert (await user.post("/admin/test-data", json=PAYLOAD)).status_code == 403
    assert (await user.post("/admin/test-data/remove-all")).status_code == 403
    assert (await user.delete(f"/admin/test-data/{uuid.uuid4()}")).status_code == 403
    assert no_storage == []
    for role in ("admin", "superadmin"):
        await set_role(user, role)
        assert (await user.get("/admin/test-data")).status_code == 200


async def test_create_builds_labelled_accounts_that_cannot_log_in(make_user, no_storage, anon):
    admin = await make_user()
    await set_role(admin, "admin")
    batch_id = await make_batch(admin)
    listed = next(b for b in (await admin.get("/admin/test-data")).json() if b["id"] == batch_id)
    assert listed["status"] == "ready" and listed["user_count"] == 3 and listed["post_count"] == 4
    async with SessionLocal() as s:
        people = list((await s.execute(select(User).where(User.test_batch_id == uuid.UUID(batch_id)))).scalars().unique())
    assert len(people) == 3
    assert all(u.password_hash is None and u.email.endswith(".invalid") and u.role == "user" for u in people)
    res = await anon.post("/api/v1/auth/login", json={"identifier": people[0].username, "password": "anything at all"})
    assert res.status_code == 401
    await admin.delete(f"/admin/test-data/{batch_id}")
    await test_data.remove_batch(uuid.UUID(batch_id))


async def test_removal_deletes_the_batch_and_keeps_real_data_correct(make_user, make_post, no_storage):
    admin, real = await make_user(), await make_user()
    await set_role(admin, "admin")
    real_post = await make_post(real, "my real post")
    batch_id = await make_batch(admin)

    async with SessionLocal() as s:
        rows = list((await s.execute(select(User).where(User.test_batch_id == uuid.UUID(batch_id)))).scalars().unique())
        test_user = rows[0]
        test_post = (await s.execute(select(Post).where(Post.author_id == test_user.id))).scalars().unique().first()
        test_ids = [u.id for u in rows]
    # A real person interacts with test content, and a test account's data touches a real post.
    assert (await real.post(f"/users/{test_user.username}/follow")).status_code == 200
    assert (await real.post(f"/posts/{test_post.id}/like")).status_code == 200
    assert (await real.post(f"/posts/{test_post.id}/comments", json={"body": "hi"})).status_code == 201
    assert (await real.post(f"/posts/{test_post.id}/save", json={})).status_code == 204
    assert (await real.get("/auth/me")).json()["following_count"] == 1

    assert (await admin.delete(f"/admin/test-data/{batch_id}")).status_code == 202
    assert (await admin.delete(f"/admin/test-data/{batch_id}")).status_code == 409  # already removing
    await test_data.remove_batch(uuid.UUID(batch_id))

    async with SessionLocal() as s:
        assert (await s.get(TestDataBatch, uuid.UUID(batch_id))).status == "removed"
        assert not (await s.execute(select(User).where(User.id.in_(test_ids)))).first()
        assert not (await s.execute(select(Post).where(Post.author_id.in_(test_ids)))).first()
        tag = await s.get(Hashtag, "test")
        assert tag is None or tag.post_count >= 0
    assert (await real.get(f"/posts/{real_post}")).status_code == 200
    me = (await real.get("/auth/me")).json()
    assert me["following_count"] == 0 and me["post_count"] == 1
    assert (await real.get(f"/posts/{test_post.id}")).status_code == 404
    assert (await real.get("/saved")).json()["items"] == []
    assert (await real.get("/users/me/export")).json()["following"] == []


async def test_remove_all_only_marks_batches_and_never_real_users(make_user, make_post, no_storage):
    admin, real = await make_user(), await make_user()
    await set_role(admin, "admin")
    post = await make_post(real)
    batch_id = await make_batch(admin)
    res = await admin.post("/admin/test-data/remove-all")
    assert res.status_code == 202 and res.json()["batches"] >= 1
    await test_data.remove_batch(uuid.UUID(batch_id))
    assert (await real.get(f"/posts/{post}")).status_code == 200
    assert (await admin.get("/auth/me")).status_code == 200


async def test_role_rules(make_user):
    plain, admin, boss, other = await make_user(), await make_user(), await make_user(), await make_user()
    await set_role(admin, "admin")
    await set_role(boss, "superadmin")
    body = {"role": "admin"}
    assert (await plain.patch(f"/admin/users/{other.id}/role", json=body)).status_code == 403
    assert (await admin.patch(f"/admin/users/{other.id}/role", json=body)).status_code == 403  # admins cannot grant
    assert (await admin.get("/admin/users")).status_code == 403
    assert (await boss.patch(f"/admin/users/{other.id}/role", json=body)).json()["role"] == "admin"
    assert (await other.get("/admin/test-data")).status_code == 200
    assert (await boss.patch(f"/admin/users/{other.id}/role", json={"role": "user"})).json()["role"] == "user"
    assert (await other.get("/admin/test-data")).status_code == 403
    assert (await boss.patch(f"/admin/users/{boss.id}/role", json={"role": "user"})).status_code == 400
    assert (await boss.patch(f"/admin/users/{other.id}/role", json={"role": "superadmin"})).status_code == 422


async def test_admin_cannot_suspend_a_staff_member(make_user):
    admin, boss, reporter = await make_user(), await make_user(), await make_user()
    await set_role(admin, "admin")
    await set_role(boss, "superadmin")
    report = (await reporter.post("/reports", json={"entity_type": "user", "entity_id": boss.id, "reason": "spam"})).json()
    res = await admin.post(f"/admin/reports/{report['id']}/resolve", json={"action": "suspend_user"})
    assert res.status_code == 403
    assert (await boss.get("/auth/me")).status_code == 200
