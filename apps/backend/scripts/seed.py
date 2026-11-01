"""Demo data for local testing. Refuses to run outside local. Run: python -m scripts.seed"""
import asyncio
import io
import math
import os
import random
import uuid

from PIL import Image, ImageDraw, ImageFilter

from app import models  # noqa: F401
from app.ai.rag.ingest import ingest_help_docs
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.core.storage import internal
from app.modules.follows.models import Follow
from app.modules.media.models import MediaAsset
from app.modules.posts.models import Post, PostMedia
from app.modules.users import repository as users
from app.modules.users.models import Profile, User
from app.workers.media_tasks import process_asset
from app.workers.ai_tasks import _enrich

PASSWORD = os.environ.get("SEED_PASSWORD", "RedStarDemo#2026")
PEOPLE = [
    ("demo", "Demo User", "Trying out RedStarVibe", "#C8102E", "admin"),
    ("asha", "Asha Rao", "Mountains, chai and film cameras", "#E4572E", "user"),
    ("kabir", "Kabir Singh", "Street photography from Delhi", "#2E86AB", "user"),
    ("meera", "Meera Nair", "Kerala coast and everything green", "#3BA99C", "user"),
    ("rohan", "Rohan Das", "Food, football and long drives", "#F2A541", "user"),
]
POSTS = [
    ("asha", "Sunset at Varkala beach. Worth the 5 am train. #sunset #beach #kerala", "Varkala", "sunset"),
    ("kabir", "Morning light in the old city lanes #street #delhi", "Old Delhi", "city"),
    ("meera", "Monsoon greens in Munnar #nature #kerala #monsoon", "Munnar", "hills"),
    ("rohan", "Night drive with @asha and the best highway views #roadtrip", "Pune", "night"),
    ("asha", "First snow on the pass. Cold fingers, happy heart #mountains", "Spiti", "snow"),
    ("kabir", "Rain, reflections and rickshaws #street #monsoon", "Kolkata", "city"),
    ("meera", "Backwaters at golden hour #sunset #kerala", "Alleppey", "sunset"),
    ("rohan", "Sunday football under the floodlights #football", "Mumbai", "night"),
    ("demo", "Hello RedStarVibe! My first post #hello", "Bengaluru", "hills"),
]
THEMES = {
    "sunset": ((252, 110, 60), (60, 30, 90)),
    "city": ((120, 150, 180), (40, 45, 60)),
    "hills": ((150, 210, 170), (20, 90, 70)),
    "night": ((25, 30, 70), (5, 5, 20)),
    "snow": ((225, 235, 245), (120, 150, 190)),
}


def artwork(theme: str, seed: int, size: tuple[int, int] = (1080, 1350)) -> bytes:
    """Generates an original placeholder picture, so no third party photos are needed."""
    rng = random.Random(seed)
    w, h = size
    top, bottom = THEMES[theme]
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(h):
        t = y / h
        draw.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom, strict=True)))
    if theme in {"sunset", "snow"}:
        cx, cy, r = rng.randint(250, 830), rng.randint(350, 650), rng.randint(90, 170)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 225, 150))
    if theme == "night":
        for _ in range(180):
            x, y = rng.randint(0, w), rng.randint(0, h // 2)
            draw.point((x, y), fill=(255, 255, 255))
    for layer in range(3):
        base = int(h * (0.62 + layer * 0.12))
        shade = tuple(max(0, int(c * (0.6 - layer * 0.18))) for c in bottom)
        phase, amp = rng.random() * 6, rng.randint(40, 110)
        points = [(0, h)] + [(x, base + int(amp * math.sin(x / 150 + phase))) for x in range(0, w + 20, 20)] + [(w, h)]
        draw.polygon(points, fill=shade)
    buffer = io.BytesIO()
    image.filter(ImageFilter.GaussianBlur(0.6)).save(buffer, "JPEG", quality=88)
    return buffer.getvalue()


async def make_asset(s, owner: uuid.UUID, purpose: str, data: bytes) -> MediaAsset:  # type: ignore[no-untyped-def]
    asset_id = uuid.uuid4()
    from app.core.ids import uuid7

    asset_id = uuid7()
    key = f"{owner}/{asset_id}"
    internal().put_object(Bucket=settings.s3_raw_bucket, Key=key, Body=data, ContentType="image/jpeg")
    asset = MediaAsset(
        id=asset_id, owner_id=owner, purpose=purpose, kind="image", raw_key=key,
        declared_type="image/jpeg", size_bytes=len(data),
    )
    s.add(asset)
    await s.commit()
    await process_asset(asset_id)
    await s.refresh(asset)
    return asset


async def main() -> None:
    if settings.is_prod:
        raise SystemExit("Refusing to seed demo accounts in a production environment")
    async with SessionLocal() as s:
        if await users.by_username(s, "demo"):
            print("Already seeded")
            return
        pw = hash_password(PASSWORD)
        people: dict[str, User] = {}
        for i, (username, name, bio, colour, role) in enumerate(PEOPLE):
            user = User(
                username=username, email=f"{username}@example.com", password_hash=pw, status="active", role=role,
                date_of_birth=__import__("datetime").date(1995, 1, 1),
            )
            await users.add_user(s, user, Profile(display_name=name, bio=bio))
            await s.commit()
            people[username] = user
            r, g, b = int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16)
            img = Image.new("RGB", (400, 400), (r, g, b))
            d = ImageDraw.Draw(img)
            d.ellipse([130, 90, 270, 230], fill=(255, 255, 255))
            d.ellipse([70, 250, 330, 520], fill=(255, 255, 255))
            buffer = io.BytesIO()
            img.save(buffer, "JPEG", quality=90)
            avatar = await make_asset(s, user.id, "avatar", buffer.getvalue())
            user = await users.by_id(s, user.id)
            user.profile.avatar_key = avatar.variants["images"][-1]["webp"]
            await s.commit()
            print("user", username, i)
        # Everyone follows everyone, except that demo starts by following two people.
        for a in people.values():
            for b in people.values():
                if a.id == b.id or (a.username == "demo" and b.username not in {"asha", "kabir"}):
                    continue
                s.add(Follow(follower_id=a.id, followee_id=b.id, status="active"))
                await users.bump_counts(s, a.id, following_count=1)
                await users.bump_counts(s, b.id, follower_count=1)
        await s.commit()
        for i, (username, caption, place, theme) in enumerate(POSTS):
            author = people[username]
            asset = await make_asset(s, author.id, "post", artwork(theme, i))
            post = Post(author_id=author.id, caption=caption, location=place, status="processing")
            post.media = [PostMedia(asset_id=asset.id, position=0)]
            s.add(post)
            await s.commit()
            await _enrich(post.id)
            print("post", caption[:30])
        await ingest_help_docs(s)
    print(f"Seeded. Log in as demo with password {PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
