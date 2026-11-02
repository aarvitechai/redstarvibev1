"""Dashboards, the full report list, CSV export and the audit log."""
import uuid
from unittest.mock import AsyncMock, patch


async def _staff(make_user, role):
    from app.core.database import SessionLocal
    from app.modules.users.models import User

    actor = await make_user()
    async with SessionLocal() as s:
        (await s.get(User, uuid.UUID(actor.id))).role = role
        await s.commit()
    return actor


async def _report(reporter, entity_type, entity_id, reason="spam", details=None):
    body = {"entity_type": entity_type, "entity_id": entity_id, "reason": reason, "details": details}
    res = await reporter.post("/reports", json=body)
    assert res.status_code in {200, 201, 202, 204}, res.text


async def _find(admin, **params):
    res = await admin.get("/admin/reports", params=params | {"limit": 100})
    assert res.status_code == 200, res.text
    return res.json()["items"]


async def test_each_dashboard_is_limited_to_its_role(make_user):
    user, admin, owner = await make_user(), await _staff(make_user, "admin"), await _staff(make_user, "superadmin")
    for path in ("/admin/dashboard", "/admin/reports", "/admin/reports/counts", "/admin/reports/export"):
        assert (await user.get(path)).status_code == 403, path
        assert (await admin.get(path)).status_code == 200, path
    for path in ("/admin/platform", "/admin/audit"):
        assert (await user.get(path)).status_code == 403, path
        assert (await admin.get(path)).status_code == 403, path
        assert (await owner.get(path)).status_code == 200, path


async def test_dashboard_counts_and_fills_quiet_days(make_user, make_post):
    admin = await _staff(make_user, "admin")
    before = (await admin.get("/admin/dashboard", params={"days": 7})).json()
    author = await make_user()
    await make_post(author, caption="dashboard post")
    after = (await admin.get("/admin/dashboard", params={"days": 7})).json()
    assert after["new_posts"] == before["new_posts"] + 1
    assert after["new_users"] == before["new_users"] + 1
    assert len(after["users_by_day"]) == 7
    assert after["users_by_day"][-1]["count"] >= 1
    assert (await admin.get("/admin/dashboard", params={"days": 5})).status_code == 422


async def test_dashboard_leaves_out_test_accounts(make_user, make_post):
    from app.core.database import SessionLocal
    from app.modules.admin.models import TestDataBatch
    from app.modules.users.models import User

    admin = await _staff(make_user, "admin")
    fake = await make_user()
    await make_post(fake)
    before = (await admin.get("/admin/dashboard")).json()
    async with SessionLocal() as s:
        batch = TestDataBatch(label="x", params={})
        s.add(batch)
        await s.flush()
        (await s.get(User, uuid.UUID(fake.id))).test_batch_id = batch.id
        await s.commit()
    after = (await admin.get("/admin/dashboard")).json()
    assert after["users"] == before["users"] - 1
    assert after["posts"] == before["posts"] - 1
    assert after["test_accounts"] == before["test_accounts"] + 1


async def test_report_list_filters_previews_and_history(make_user, make_post):
    admin = await _staff(make_user, "admin")
    author, reporter = await make_user(), await make_user()
    post_id = await make_post(author, caption="reported caption")
    await _report(reporter, "post", post_id, "hate", "looks bad")
    await _report(reporter, "user", author.id, "spam")

    rows = [r for r in await _find(admin, status="open", reason="hate") if r["entity_id"] == post_id]
    assert len(rows) == 1
    row = rows[0]
    assert row["reporter"] == reporter.username
    assert row["target"]["author"] == author.username and "reported caption" in row["target"]["text"]
    assert row["target"]["link"] == f"/p/{post_id}"
    assert all(r["entity_type"] == "user" for r in await _find(admin, status="all", entity_type="user"))

    assert (await admin.post(f"/admin/reports/{row['id']}/resolve", json={"action": "dismiss"})).status_code == 204
    assert row["id"] not in [r["id"] for r in await _find(admin, status="open")]
    done = [r for r in await _find(admin, status="dismissed") if r["id"] == row["id"]][0]
    assert done["resolved_by_name"] == admin.username and done["resolved_at"]
    assert (await admin.post(f"/admin/reports/{row['id']}/resolve", json={"action": "dismiss"})).status_code == 409


async def test_removing_a_post_closes_its_other_reports_and_fixes_counts(make_user, make_post):
    admin = await _staff(make_user, "admin")
    author, one, two, follower = await make_user(), await make_user(), await make_user(), await make_user()
    post_id = await make_post(author)
    await _report(one, "post", post_id)
    await _report(two, "post", post_id)
    first = [r for r in await _find(admin, status="open") if r["entity_id"] == post_id]
    assert len(first) == 2
    with patch("app.modules.admin.service.emit", AsyncMock()):
        res = await admin.post(f"/admin/reports/{first[0]['id']}/resolve", json={"action": "remove_content"})
    assert res.status_code == 204, res.text
    assert not [r for r in await _find(admin, status="open") if r["entity_id"] == post_id]
    assert (await follower.get(f"/posts/{post_id}")).status_code == 404
    assert (await author.get(f"/users/{author.username}")).json()["post_count"] == 0


async def test_removing_a_comment_really_removes_it(make_user, make_post):
    admin = await _staff(make_user, "admin")
    author, rude = await make_user(), await make_user()
    post_id = await make_post(author)
    comment = (await rude.post(f"/posts/{post_id}/comments", json={"body": "nasty"})).json()
    await _report(author, "comment", comment["id"])
    row = [r for r in await _find(admin, status="open") if r["entity_id"] == comment["id"]][0]
    assert row["target"]["text"] == "nasty"
    assert (await admin.post(f"/admin/reports/{row['id']}/resolve", json={"action": "remove_content"})).status_code == 204
    assert (await author.get(f"/posts/{post_id}/comments")).json()["items"] == []
    assert (await author.get(f"/posts/{post_id}")).json()["comment_count"] == 0


async def test_remove_content_is_refused_when_there_is_nothing_to_remove(make_user):
    admin = await _staff(make_user, "admin")
    target, reporter = await make_user(), await make_user()
    await _report(reporter, "user", target.id)
    row = [r for r in await _find(admin, status="open") if r["entity_id"] == target.id][0]
    res = await admin.post(f"/admin/reports/{row['id']}/resolve", json={"action": "remove_content"})
    assert res.status_code == 400
    assert row["id"] in [r["id"] for r in await _find(admin, status="open")]


async def test_csv_export_neutralises_formulas():
    from app.modules.admin.reports import csv_safe

    assert csv_safe("=HYPERLINK('x')") == "'=HYPERLINK('x')"
    assert csv_safe("@cmd") == "'@cmd"
    assert csv_safe("normal") == "normal"
    assert csv_safe(None) == ""


async def test_export_contains_filtered_rows_and_is_audited(make_user, make_post):
    admin, owner = await _staff(make_user, "admin"), await _staff(make_user, "superadmin")
    reporter = await make_user()
    post_id = await make_post(await make_user())
    await _report(reporter, "post", post_id, "other", "=SUM(A1)")
    res = await admin.get("/admin/reports/export", params={"status": "open", "reason": "other"})
    assert res.headers["content-type"].startswith("text/csv")
    assert "attachment" in res.headers["content-disposition"]
    assert post_id in res.text and "'=SUM(A1)" in res.text

    audit = (await owner.get("/admin/audit", params={"category": "admin"})).json()["items"]
    assert audit[0]["action"] == "admin.reports.export" and audit[0]["actor"] == admin.username


async def test_platform_shows_staff_and_services(make_user):
    admin, owner = await _staff(make_user, "admin"), await _staff(make_user, "superadmin")
    data = (await owner.get("/admin/platform")).json()
    assert {admin.username, owner.username} <= {row["username"] for row in data["staff"]}
    assert data["database_ok"] is True and data["redis_ok"] is True
    assert [q["name"] for q in data["queue_depth"]] == ["default", "media", "ai"]
    assert data["staff_without_mfa"] >= 2


async def test_audit_filter_and_paging(make_user, anon):
    owner = await _staff(make_user, "superadmin")
    victim = await make_user()
    for _ in range(3):
        await anon.post("/api/v1/auth/login", json={"identifier": victim.username, "password": "wrong password 1"})
    first = (await owner.get("/admin/audit", params={"category": "auth", "limit": 2})).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    assert all(row["action"].startswith("auth.") for row in first["items"])
    second = (await owner.get("/admin/audit", params={"category": "auth", "limit": 2, "cursor": first["next_cursor"]})).json()
    assert not {r["id"] for r in first["items"]} & {r["id"] for r in second["items"]}
    assert (await owner.get("/admin/audit", params={"category": "admin%' OR 1=1"})).status_code == 422
