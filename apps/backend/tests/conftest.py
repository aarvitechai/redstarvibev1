"""Integration tests run against real Postgres and Redis (compose locally, service containers in CI)."""
import itertools
import os

import httpx
import pytest

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("BREACHED_PASSWORD_CHECK", "false")

from app.main import app  # noqa: E402

counter = itertools.count(int(__import__("time").time()) % 1_000_000)
PASSWORD = "correct horse battery 9"


class Actor:
    def __init__(self, client: httpx.AsyncClient, username: str, user_id: str) -> None:
        self.c, self.username, self.id = client, username, user_id

    def _h(self) -> dict[str, str]:
        return {"x-csrf-token": self.c.cookies.get("rsv_csrf", "")}

    async def post(self, url, **kw):  # noqa: ANN001, ANN201
        return await self.c.post(f"/api/v1{url}", headers=self._h() | kw.pop("headers", {}), **kw)

    async def patch(self, url, **kw):  # noqa: ANN001, ANN201
        return await self.c.patch(f"/api/v1{url}", headers=self._h(), **kw)

    async def put(self, url, **kw):  # noqa: ANN001, ANN201
        return await self.c.put(f"/api/v1{url}", headers=self._h(), **kw)

    async def delete(self, url, **kw):  # noqa: ANN001, ANN201
        return await self.c.delete(f"/api/v1{url}", headers=self._h(), **kw)

    async def get(self, url, **kw):  # noqa: ANN001, ANN201
        return await self.c.get(f"/api/v1{url}", **kw)


@pytest.fixture
async def anon():
    transport = httpx.ASGITransport(app=app)
    ip = f"10.8.{next(counter) % 250}.{next(counter) % 250}"
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers={"x-real-ip": ip}) as client:
        yield client


@pytest.fixture
async def make_user():
    """Creates an active user directly, then logs in over HTTP so cookies and CSRF are real."""
    from app.core.database import SessionLocal
    from app.core.security import hash_password
    from app.modules.users import repository as users
    from app.modules.users.models import Profile, User

    clients = []

    async def _make(private: bool = False) -> Actor:
        n = next(counter)
        username = f"t{n}"
        async with SessionLocal() as s:
            user = User(
                username=username, email=f"{username}@example.com", password_hash=hash_password(PASSWORD),
                status="active", is_private=private,
            )
            await users.add_user(s, user, Profile(display_name=username))
            await s.commit()
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        clients.append(client)
        res = await client.post(
            "/api/v1/auth/login", json={"identifier": username, "password": PASSWORD},
            headers={"x-real-ip": f"10.9.{n % 250}.{n % 199}"},
        )
        assert res.status_code == 200, res.text
        return Actor(client, username, res.json()["id"])

    yield _make
    for client in clients:
        await client.aclose()


@pytest.fixture
async def make_post():
    """A published post created through the database, skipping the media worker."""
    import uuid

    from app.core.database import SessionLocal
    from app.modules.media.models import MediaAsset
    from app.modules.posts.models import Post, PostMedia
    from app.modules.users import repository as users

    async def _make(author: Actor, caption: str = "hello", visibility: str = "public", status: str = "published"):  # noqa: ANN202
        async with SessionLocal() as s:
            owner = uuid.UUID(author.id)
            asset = MediaAsset(
                owner_id=owner, purpose="post", kind="image", raw_key=f"{owner}/x", declared_type="image/jpeg",
                size_bytes=1, status="ready", width=10, height=10,
                variants={"images": [{"w": 10, "webp": "x.webp", "avif": "x.avif"}]},
            )
            s.add(asset)
            await s.flush()
            post = Post(author_id=owner, caption=caption, visibility=visibility, status=status)
            post.media = [PostMedia(asset_id=asset.id, position=0)]
            s.add(post)
            await users.bump_counts(s, owner, post_count=1)
            await s.commit()
            return str(post.id)

    return _make
