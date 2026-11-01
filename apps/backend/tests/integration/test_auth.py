import pyotp

from tests.conftest import PASSWORD


async def signup_payload(n: str) -> dict:
    return {
        "email": f"{n}@example.com", "username": n, "password": "a long unusual passphrase 7",
        "date_of_birth": "2000-01-01", "display_name": "New",
    }


async def test_signup_requires_verified_email(anon, monkeypatch):
    sent = {}

    async def fake_enqueue(task, *args, queue="default"):
        sent[task] = args

    monkeypatch.setattr("app.modules.auth.service.enqueue", fake_enqueue)
    import time

    name = f"su{int(time.time() * 1000) % 10**9}"
    assert (await anon.post("/api/v1/auth/signup", json=await signup_payload(name))).status_code == 202
    login = await anon.post("/api/v1/auth/login", json={"identifier": name, "password": "a long unusual passphrase 7"})
    assert login.status_code == 403 and login.json()["error"]["code"] == "email_unverified"

    code = sent["notifications.send_email"][1].split()[0]
    wrong = "000000" if code != "000000" else "111111"
    bad = await anon.post("/api/v1/auth/verify-email", json={"email": f"{name}@example.com", "code": wrong})
    assert bad.status_code == 400
    ok = await anon.post("/api/v1/auth/verify-email", json={"email": f"{name}@example.com", "code": code})
    assert ok.status_code == 200 and ok.json()["username"] == name
    assert "rsv_access" in ok.cookies


async def test_under_13_rejected(anon):
    payload = await signup_payload("youngster1")
    payload["date_of_birth"] = "2020-01-01"
    res = await anon.post("/api/v1/auth/signup", json=payload)
    assert res.status_code == 400 and res.json()["error"]["code"] == "too_young"


async def test_short_and_common_passwords_rejected(anon):
    payload = await signup_payload("weakpass1")
    payload["password"] = "short"
    assert (await anon.post("/api/v1/auth/signup", json=payload)).status_code == 422
    payload["password"] = "password123"
    assert (await anon.post("/api/v1/auth/signup", json=payload)).json()["error"]["code"] == "weak_password"


async def test_error_body_shape(anon):
    res = await anon.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert set(res.json()["error"]) == {"code", "message", "request_id"}
    assert res.json()["error"]["request_id"]


async def test_wrong_password(make_user, anon):
    user = await make_user()
    res = await anon.post("/api/v1/auth/login", json={"identifier": user.username, "password": "nope nope nope"})
    assert res.status_code == 401 and res.json()["error"]["code"] == "invalid_credentials"


async def test_csrf_required_on_cookie_writes(make_user):
    user = await make_user()
    res = await user.c.patch("/api/v1/users/me", json={"bio": "no token"})
    assert res.status_code == 403 and res.json()["error"]["code"] == "csrf_failed"
    assert (await user.patch("/users/me", json={"bio": "with token"})).status_code == 200


async def test_refresh_rotates_and_reuse_revokes_family(make_user):
    user = await make_user()
    old = user.c.cookies.get("rsv_refresh")
    assert (await user.post("/auth/refresh")).status_code == 200
    new = user.c.cookies.get("rsv_refresh")
    assert old != new

    from datetime import UTC, datetime, timedelta

    from sqlalchemy import update

    from app.core.database import SessionLocal
    from app.core.security import hash_token
    from app.modules.auth.models import RefreshToken

    async with SessionLocal() as s:  # move past the concurrent tab grace period
        await s.execute(
            update(RefreshToken).where(RefreshToken.token_hash == hash_token(old))
            .values(used_at=datetime.now(UTC) - timedelta(minutes=5))
        )
        await s.commit()
    user.c.cookies.set("rsv_refresh", old, path="/api/v1/auth")
    assert (await user.post("/auth/refresh")).status_code == 401
    user.c.cookies.set("rsv_refresh", new, path="/api/v1/auth")
    assert (await user.post("/auth/refresh")).status_code == 401  # the whole family is dead


async def test_logout_denies_access_token(make_user):
    user = await make_user()
    token = user.c.cookies.get("rsv_access")
    assert (await user.post("/auth/logout")).status_code == 204
    res = await user.c.get("/api/v1/auth/me", headers={"authorization": f"Bearer {token}"})
    assert res.status_code == 401


async def test_totp_flow(make_user, anon):
    user = await make_user()
    setup = (await user.post("/auth/mfa/totp/setup")).json()
    assert (await user.post("/auth/mfa/totp/enable", json={"code": "000000"})).status_code == 400
    code = pyotp.TOTP(setup["secret"]).now()
    assert (await user.post("/auth/mfa/totp/enable", json={"code": code})).status_code == 204
    res = await anon.post("/api/v1/auth/login", json={"identifier": user.username, "password": PASSWORD})
    assert res.status_code == 401 and res.json()["error"]["code"] == "mfa_required"
    res = await anon.post("/api/v1/auth/login", json={
        "identifier": user.username, "password": PASSWORD, "totp_code": pyotp.TOTP(setup["secret"]).now(),
    })
    assert res.status_code == 200


async def test_failed_logins_lock_but_successful_ones_do_not(make_user, anon):
    user = await make_user()
    for _ in range(12):
        ok = await user.post("/auth/login", json={"identifier": user.username, "password": PASSWORD})
        assert ok.status_code == 200
    statuses = []
    for _ in range(11):
        res = await anon.post("/api/v1/auth/login", json={"identifier": user.username, "password": "wrong wrong wrong"})
        statuses.append(res.status_code)
    assert statuses[:10] == [401] * 10 and statuses[10] == 429
    blocked = await anon.post("/api/v1/auth/login", json={"identifier": user.username, "password": PASSWORD})
    assert blocked.status_code == 429
