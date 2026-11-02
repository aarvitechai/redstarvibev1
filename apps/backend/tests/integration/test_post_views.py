"""A view counts once per person per post per day."""
import httpx

from app.main import app


def _visitor(ip: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers={"x-real-ip": ip})


async def test_logged_in_viewer_counts_once(make_user, make_post):
    author, viewer = await make_user(), await make_user()
    post_id = await make_post(author)
    first = (await viewer.post(f"/posts/{post_id}/view")).json()
    assert first == {"view_count": 1, "counted": True}
    again = (await viewer.post(f"/posts/{post_id}/view")).json()
    assert again == {"view_count": 1, "counted": False}
    assert (await author.get(f"/posts/{post_id}")).json()["view_count"] == 1


async def test_author_views_do_not_count(make_user, make_post):
    author = await make_user()
    post_id = await make_post(author)
    assert (await author.post(f"/posts/{post_id}/view")).json() == {"view_count": 0, "counted": False}


async def test_visitor_is_counted_by_cookie(make_user, make_post):
    post_id = await make_post(await make_user())
    async with _visitor("10.20.0.1") as one, _visitor("10.20.0.2") as two:
        res = await one.post(f"/api/v1/posts/{post_id}/view")
        assert res.json() == {"view_count": 1, "counted": True}
        cookie = res.headers["set-cookie"].lower()
        assert "rsv_visitor=" in cookie and "httponly" in cookie and "samesite=lax" in cookie and "path=/api/v1/posts" in cookie

        again = await one.post(f"/api/v1/posts/{post_id}/view")
        assert again.json()["counted"] is False
        assert "set-cookie" not in again.headers

        assert (await two.post(f"/api/v1/posts/{post_id}/view")).json() == {"view_count": 2, "counted": True}


async def test_a_bad_cookie_is_replaced(make_user, make_post):
    post_id = await make_post(await make_user())
    async with _visitor("10.20.0.3") as client:
        client.cookies.set("rsv_visitor", "not-valid|injected")
        res = await client.post(f"/api/v1/posts/{post_id}/view")
    assert res.json()["counted"] is True
    assert "not-valid" not in res.headers["set-cookie"]


async def test_clearing_cookies_cannot_add_views_when_logged_in(make_user, make_post):
    author, viewer = await make_user(), await make_user()
    post_id = await make_post(author)
    await viewer.post(f"/posts/{post_id}/view")
    viewer.c.cookies.delete("rsv_visitor")
    assert (await viewer.post(f"/posts/{post_id}/view")).json()["counted"] is False


async def test_many_new_cookies_from_one_ip_stop_counting(make_user, make_post):
    from app.modules.posts import service

    post_id = await make_post(await make_user())
    limit, service.VIEW_IP_LIMIT = service.VIEW_IP_LIMIT, 2
    try:
        results = []
        for _ in range(4):
            async with _visitor("10.20.0.4") as client:
                res = await client.post(f"/api/v1/posts/{post_id}/view")
                assert res.status_code == 200
                results.append(res.json()["counted"])
    finally:
        service.VIEW_IP_LIMIT = limit
    assert results == [True, True, False, False]


async def test_views_on_hidden_posts_are_refused(make_user, make_post, anon):
    author, other = await make_user(), await make_user()
    draft = await make_post(author, status="draft")
    assert (await other.post(f"/posts/{draft}/view")).status_code == 404
    followers_only = await make_post(author, visibility="followers")
    assert (await anon.post(f"/api/v1/posts/{followers_only}/view")).status_code == 404
    assert (await author.get(f"/posts/{followers_only}")).json()["view_count"] == 0
