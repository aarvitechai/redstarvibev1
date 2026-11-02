"""Permission map, staff limits, tickets, verification, plans, ad review and business staff."""
import uuid

from app.core.permissions import has_permission
from tests.integration.test_admin_dashboards import _find, _report, _staff


def test_permission_table_matches_the_spec():
    table = {
        "manage_admins": {"superadmin"}, "manage_plans": {"superadmin"}, "view_revenue": {"superadmin"},
        "verify_accounts": {"superadmin", "admin"}, "remove_reported": {"superadmin", "admin"},
        "approve_ads": {"superadmin", "admin"},
        "resolve_tickets": {"superadmin", "admin", "staff"}, "moderate_first_level": {"superadmin", "admin", "staff"},
        "escalate": {"staff"}, "manage_business": {"business"},
    }
    for permission, allowed in table.items():
        for role in ("superadmin", "admin", "staff", "business", "user"):
            assert has_permission(role, permission) == (role in allowed), (role, permission)
    assert not has_permission("nonsense", "escalate")


async def test_me_lists_permissions(make_user):
    staff = await _staff(make_user, "staff")
    me = (await staff.get("/auth/me")).json()
    assert "escalate" in me["permissions"] and "remove_reported" not in me["permissions"]


async def test_staff_can_dismiss_and_escalate_but_not_remove(make_user, make_post):
    staff, admin = await _staff(make_user, "staff"), await _staff(make_user, "admin")
    author, reporter = await make_user(), await make_user()
    post_id = await make_post(author)
    await _report(reporter, "post", post_id)
    row = [r for r in await _find(staff, status="open") if r["entity_id"] == post_id][0]

    for action in ("remove_content", "suspend_user"):
        assert (await staff.post(f"/admin/reports/{row['id']}/resolve", json={"action": action})).status_code == 403
    for path in ("/admin/dashboard", "/admin/reports/export", "/admin/verification", "/admin/ads"):
        assert (await staff.get(path)).status_code == 403, path

    assert (await staff.post(f"/admin/reports/{row['id']}/escalate")).status_code == 204
    escalated = [r for r in await _find(admin, status="open") if r["id"] == row["id"]][0]
    assert escalated["escalated_by_name"] == staff.username
    assert (await admin.post(f"/admin/reports/{row['id']}/escalate")).status_code == 403  # the table gives this to staff only
    assert (await admin.post(f"/admin/reports/{row['id']}/resolve", json={"action": "dismiss"})).status_code == 204


async def test_role_changes_include_staff_and_business(make_user):
    owner, admin = await _staff(make_user, "superadmin"), await _staff(make_user, "admin")
    target = await make_user()
    assert (await admin.patch(f"/admin/users/{target.id}/role", json={"role": "staff"})).status_code == 403
    assert (await owner.patch(f"/admin/users/{target.id}/role", json={"role": "staff"})).json()["role"] == "staff"
    assert (await owner.patch(f"/admin/users/{target.id}/role", json={"role": "business"})).json()["role"] == "business"
    assert (await owner.patch(f"/admin/users/{target.id}/role", json={"role": "superadmin"})).status_code == 422


async def test_ticket_flow_and_privacy(make_user):
    user, other = await make_user(), await make_user()
    staff, admin = await _staff(make_user, "staff"), await _staff(make_user, "admin")
    made = await user.post("/support/tickets", json={"subject": "Cannot upload", "body": "It fails"})
    assert made.status_code == 201, made.text
    tid = made.json()["id"]
    assert (await other.get(f"/support/tickets/{tid}")).status_code == 404
    assert (await other.post(f"/support/tickets/{tid}/messages", json={"body": "hi"})).status_code == 404
    assert (await user.get("/admin/tickets")).status_code == 403
    assert tid in [t["id"] for t in (await staff.get("/admin/tickets")).json()["items"]]

    assert (await staff.post(f"/support/tickets/{tid}/messages", json={"body": "We are checking"})).status_code == 201
    seen = (await user.get(f"/support/tickets/{tid}")).json()["messages"]
    assert seen[-1]["author"] == "Support" and seen[-1]["is_staff"] is True  # the employee stays anonymous

    assert (await user.post(f"/admin/tickets/{tid}/escalate")).status_code == 403
    assert (await staff.post(f"/admin/tickets/{tid}/escalate")).json()["status"] == "escalated"
    assert (await staff.post(f"/admin/tickets/{tid}/resolve")).status_code == 403
    assert (await admin.post(f"/admin/tickets/{tid}/resolve")).json()["status"] == "resolved"
    reopened = await user.post(f"/support/tickets/{tid}/messages", json={"body": "Still broken"})
    assert reopened.json()["status"] == "open"


async def test_business_verification_grants_the_role_and_badge(make_user):
    user, admin = await make_user(), await _staff(make_user, "admin")
    body = {"kind": "business", "details": "Sharma Welding, GST 27ABCDE1234F1Z5"}
    made = await user.post("/verification", json=body)
    assert made.status_code == 201, made.text
    assert (await user.post("/verification", json=body)).status_code == 409
    assert (await user.get("/business/ads")).status_code == 403
    assert (await user.post(f"/admin/verification/{made.json()['id']}/review", json={"approve": True})).status_code == 403

    res = await admin.post(f"/admin/verification/{made.json()['id']}/review", json={"approve": True})
    assert res.json()["status"] == "approved"
    me = (await user.get("/auth/me")).json()
    assert me["verified"] is True and me["role"] == "business" and "manage_business" in me["permissions"]
    assert (await user.get("/business/ads")).status_code == 200
    assert (await admin.post(f"/admin/verification/{made.json()['id']}/review", json={"approve": False})).status_code == 409


async def test_verifying_staff_never_lowers_their_role(make_user):
    staff, admin = await _staff(make_user, "staff"), await _staff(make_user, "admin")
    made = await staff.post("/verification", json={"kind": "business", "details": "Staff member's own shop"})
    await admin.post(f"/admin/verification/{made.json()['id']}/review", json={"approve": True})
    me = (await staff.get("/auth/me")).json()
    assert me["role"] == "staff" and me["verified"] is True


async def test_plans_start_without_prices_and_only_super_admin_edits(make_user, anon):
    admin, owner = await _staff(make_user, "admin"), await _staff(make_user, "superadmin")
    public = (await anon.get("/api/v1/plans")).json()
    assert [p["code"] for p in public] == ["free", "premium", "creator", "business", "enterprise"]
    body = {"price_paise": 49900, "active": True, "includes": "No ads"}
    assert (await admin.put("/admin/plans/premium", json=body)).status_code == 403
    assert (await owner.put("/admin/plans/premium", json=body)).json()["price_paise"] == 49900
    assert (await owner.put("/admin/plans/premium", json=body | {"price_paise": -1})).status_code == 422
    assert (await owner.put("/admin/plans/nope", json=body)).status_code == 404
    await owner.put("/admin/plans/enterprise", json={"price_paise": None, "active": False, "includes": "x"})
    assert "enterprise" not in [p["code"] for p in (await anon.get("/api/v1/plans")).json()]
    assert "enterprise" in [p["code"] for p in (await owner.get("/admin/plans")).json()]
    await owner.put("/admin/plans/enterprise", json={"price_paise": None, "active": True, "includes": "x"})


async def test_ad_requests_need_a_business_and_their_own_post(make_user, make_post):
    business, admin = await _staff(make_user, "business"), await _staff(make_user, "admin")
    other = await make_user()
    theirs, mine = await make_post(other), await make_post(business)
    body = {"headline": "Best welding in town", "daily_budget_paise": 50000, "city": "Pune"}
    assert (await other.post("/business/ads", json=body | {"post_id": theirs})).status_code == 403
    assert (await business.post("/business/ads", json=body | {"post_id": theirs})).status_code == 400
    made = await business.post("/business/ads", json=body | {"post_id": mine})
    assert made.status_code == 201, made.text
    assert made.json()["id"] in [a["id"] for a in (await admin.get("/admin/ads")).json()]
    assert (await business.post(f"/admin/ads/{made.json()['id']}/review", json={"approve": True})).status_code == 403
    res = await admin.post(f"/admin/ads/{made.json()['id']}/review", json={"approve": False, "reason": "Blurry"})
    assert res.json()["status"] == "rejected" and res.json()["reason"] == "Blurry"
    assert (await business.get("/business/ads")).json()[0]["reason"] == "Blurry"


async def test_business_staff_list(make_user):
    business, person, blocker = await _staff(make_user, "business"), await make_user(), await make_user()
    assert (await person.post("/business/staff", json={"username": person.username})).status_code == 403
    assert (await business.post("/business/staff", json={"username": person.username})).status_code == 204
    assert [u["username"] for u in (await business.get("/business/staff")).json()] == [person.username]
    await blocker.post(f"/users/{business.username}/block")
    assert (await business.post("/business/staff", json={"username": blocker.username})).status_code == 400
    assert (await business.post("/business/staff", json={"username": uuid.uuid4().hex})).status_code == 400
    assert (await business.delete(f"/business/staff/{person.id}")).status_code == 204
    assert (await business.get("/business/staff")).json() == []
