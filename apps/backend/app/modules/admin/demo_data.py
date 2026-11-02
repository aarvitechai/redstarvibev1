"""A large demo set for testing at scale: 100 accounts, 20,000 posts with real photos, 20 short videos, and feature data.

Photos go through the real media pipeline once, then posts reuse them, so thousands of posts stay cheap in storage and
time. Each short video is used by one post. Everything belongs to one batch, so removing the batch removes all of it.

Sources, both free to use: photos from Lorem Picsum (Unsplash License), clips cut from the Sintel and Big Buck Bunny
trailers (CC BY, (c) Blender Foundation). Do not ship these as real content.
"""
import os
import random
import secrets
import subprocess  # noqa: S404
import tempfile
import time
import uuid
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, conflict
from app.core.events import enqueue
from app.modules.admin import repository as repo
from app.modules.admin.models import TestDataBatch
from app.modules.admin.test_art import avatar
from app.modules.admin.test_data import BatchOut, _ensure_allowed, batch_out, store_and_process
from app.modules.business.models import AdRequest, VerificationRequest
from app.modules.chat.models import Conversation, ConversationMember, Message
from app.modules.comments.models import Comment
from app.modules.communities.models import Community, CommunityMember, CommunityPost
from app.modules.feed.service import invalidate_feed
from app.modules.follows.models import Follow
from app.modules.media.models import MediaAsset
from app.modules.moderation.models import Report
from app.modules.notifications.models import Notification
from app.modules.posts.models import Hashtag, Like, Post, PostCollab, PostHashtag, PostMedia, PostTag, Save
from app.modules.posts.service import extract_hashtags
from app.modules.stories.models import CloseFriend, Highlight, HighlightStory, Story, StoryAnswer, StoryReaction, StoryView
from app.modules.support.models import Ticket, TicketMessage
from app.modules.users import repository as users
from app.modules.users.models import Profile, User

log = structlog.get_logger()

DEMO_USERS = 100
DEMO_POSTS = 20_000  # includes the video posts and reels below
DEMO_VIDEO_POSTS = 5
DEMO_REELS = 15
DEMO_PHOTOS = 200
REAL_ACCOUNTS = ("demo", "owner")  # seed accounts you can log in with, so they get chats, notifications and a full feed
DEMO_STORIES = 200
MIN_PHOTOS = 20
FOLLOWS_EACH = 15
DAYS_BACK = 90
CHUNK = 1000

PICSUM_LIST = "https://picsum.photos/v2/list?page={page}&limit=100"
PICSUM_PHOTO = "https://picsum.photos/id/{id}/1080/1350.jpg"
CLIP_SOURCES = (  # address, start of each clip in seconds, clip length
    ("https://download.blender.org/durian/trailer/sintel_trailer-720p.mp4", range(3, 43, 4), 4),
    ("https://download.blender.org/peach/trailer/trailer_480p.mov", range(1, 29, 3), 3),
)
MAX_DOWNLOAD = 20 * 1024 * 1024
OVERLAY = {"x": 50, "y": 15, "size": "large", "style": "highlight", "color": "#C8102E"}

FIRST = ["Aarav", "Diya", "Vihaan", "Ananya", "Ishaan", "Kavya", "Reyansh", "Saanvi", "Arjun", "Myra", "Rohit", "Neha", "Kabir",
         "Pooja", "Aditya", "Meera", "Sahil", "Riya", "Karan", "Tara"]
LAST = ["Sharma", "Verma", "Iyer", "Nair", "Das", "Khan", "Patel", "Reddy", "Singh", "Gupta"]
LINES = [
    "Golden hour never gets old", "Morning walk through the old lanes", "Green everywhere after the rain",
    "Night drive with the windows down", "Took the long way home today", "Quiet corners are my favourite",
    "This view was worth the climb", "Coffee first, plans later", "Weekend mood, no alarms", "Found this place by accident",
    "Colours like this make my day", "A little peace before the week starts", "Could stay here all day",
    "Still thinking about this trip", "Small moments, big smiles", "Back where it all started",
]
PLACES = ["Varkala", "Old Delhi", "Munnar", "Pune", "Spiti", "Jaipur", "Goa", "Mumbai", "Udaipur", "Shillong", "Hampi",
          "Rishikesh", "Kochi", "Darjeeling", "Bengaluru", "Pondicherry"]
TAGS = ["travel", "nature", "sunset", "street", "mountains", "food", "city", "weekend", "india", "photography", "beach",
        "monsoon"]
COMMENTS = ["Love this!", "Where is this?", "So good", "Beautiful shot", "Need to go here", "Wow", "Great colours", "Saving this",
            "This made my day", "Take me there"]


class DemoIn(BaseModel):
    label: str = Field("Demo data", min_length=1, max_length=80)


def is_demo(batch: TestDataBatch) -> bool:
    return (batch.params or {}).get("kind") == "demo"


async def request_create(s: AsyncSession, admin: User, data: DemoIn, ip: str | None) -> BatchOut:
    _ensure_allowed()
    if any(is_demo(b) and b.status != "removed" for b in await repo.list_batches(s)):
        raise conflict("demo_exists", "A demo set already exists. Remove it first.")
    params = {"kind": "demo", "users": DEMO_USERS, "posts": DEMO_POSTS}
    batch = TestDataBatch(label=data.label.strip(), params=params, created_by=admin.id)
    await repo.add_batch(s, batch)
    await users.audit(s, admin.id, "admin.test_data.create", str(batch.id), ip, params)
    await s.commit()
    await enqueue("admin.create_test_batch", batch.id, queue="media")
    return batch_out(batch)


# ---- downloads: fixed addresses only, and the media pipeline still validates every file ----
def _get(client: httpx.Client, url: str) -> bytes | None:
    try:
        res = client.get(url)
    except httpx.HTTPError:
        return None
    if res.status_code != 200 or len(res.content) > MAX_DOWNLOAD:
        return None
    return res.content


def fetch_photos(count: int) -> Iterator[bytes]:
    """Yields until `count` photos arrive or the source runs out. A failed photo is skipped."""
    sent = 0
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for page in range(1, 11):
            listing = _get(client, PICSUM_LIST.format(page=page))
            if listing is None:
                return
            for entry in httpx.Response(200, content=listing).json():
                data = _get(client, PICSUM_PHOTO.format(id=int(entry["id"])))
                if data:
                    yield data
                    sent += 1
                    if sent >= count:
                        return


def _cut_clip(source: Path, start: int, seconds: int, out: Path) -> bytes | None:
    try:
        subprocess.run(  # noqa: S603
            ["ffmpeg", "-y", "-v", "error", "-ss", str(start), "-i", str(source), "-t", str(seconds),  # noqa: S607
             "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
             "-f", "mp4", str(out)],
            check=True, capture_output=True, timeout=120,
        )
    except (subprocess.SubprocessError, OSError):
        log.warning("demo_clip_skipped", start=start)
        return None
    return out.read_bytes()


def fetch_clips() -> list[bytes]:
    clips: list[bytes] = []
    with httpx.Client(timeout=120, follow_redirects=True) as client, tempfile.TemporaryDirectory(prefix="rsv-") as work:
        source, out = Path(work) / "source", Path(work) / "clip.mp4"
        for url, starts, seconds in CLIP_SOURCES:
            data = _get(client, url)
            if data is None:
                continue
            source.write_bytes(data)
            clips += [clip for start in starts if (clip := _cut_clip(source, start, seconds, out))]
    return clips


# ---- bulk creation ----
def _id_at(when: datetime) -> uuid.UUID:
    """A UUIDv7 stamped with a past time, so old posts sort as old everywhere."""
    rand = bytearray(os.urandom(10))
    rand[0] = (rand[0] & 0x0F) | 0x70
    rand[2] = (rand[2] & 0x3F) | 0x80
    return uuid.UUID(bytes=int(when.timestamp() * 1000).to_bytes(6, "big") + bytes(rand))


def _caption(rng: random.Random) -> str:
    tags = rng.sample(TAGS, rng.randint(1, 3))
    return f"{rng.choice(LINES)} " + " ".join(f"#{t}" for t in tags)


async def _insert(s: AsyncSession, model: Any, rows: list[dict[str, Any]]) -> None:
    for start in range(0, len(rows), CHUNK):
        await s.execute(insert(model), rows[start:start + CHUNK])
        await s.commit()


async def _make_people(s: AsyncSession, batch: TestDataBatch, count: int, rng: random.Random) -> list[User]:
    people: list[User] = []
    for i in range(count):
        # No password and an undeliverable address (RFC 2606), so nobody can log in as a test account.
        username = f"test_{secrets.token_hex(4)}"
        user = User(
            username=username, email=f"{username}@test-data.invalid", password_hash=None, status="active",
            date_of_birth=date(1995, 1, 1), test_batch_id=batch.id,
        )
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)} (test)"
        await users.add_user(s, user, Profile(display_name=name, bio="Test account. Not a real person."))
        batch.user_count = i + 1
        await s.commit()
        # Drawn avatars, on purpose: a stranger's real face on a fake account would be wrong.
        picture = await store_and_process(s, user.id, "avatar", avatar(i))
        user.profile.avatar_key = (picture.variants or {})["images"][-1]["webp"]
        await s.commit()
        people.append(user)
    return people


async def _make_library(s: AsyncSession, owner: User) -> tuple[list[MediaAsset], list[MediaAsset]]:
    photos: list[MediaAsset] = []
    for data in fetch_photos(DEMO_PHOTOS):
        try:
            photos.append(await store_and_process(s, owner.id, "post", data))
        except AppError:
            log.warning("demo_photo_skipped")
    if len(photos) < MIN_PHOTOS:
        raise AppError(502, "demo_media", f"Only {len(photos)} photos could be downloaded. Check the internet connection.")
    clips = [await store_and_process(s, owner.id, "reel", data, "video") for data in fetch_clips()]
    needed = DEMO_REELS + DEMO_VIDEO_POSTS
    if len(clips) < needed:
        raise AppError(502, "demo_media", f"Only {len(clips)} of {needed} video clips were made. Check the internet connection.")
    return photos, clips


async def _make_follows(s: AsyncSession, people: list[User], rng: random.Random) -> None:
    rows: list[dict[str, Any]] = []
    following: Counter[uuid.UUID] = Counter()
    followers: Counter[uuid.UUID] = Counter()
    for person in people:
        others = [p for p in people if p.id != person.id]
        for other in rng.sample(others, min(FOLLOWS_EACH, len(others))):
            rows.append({"follower_id": person.id, "followee_id": other.id, "status": "active"})
            following[person.id] += 1
            followers[other.id] += 1
    await _insert(s, Follow, rows)
    for person in people:
        await users.bump_counts(s, person.id, following_count=following[person.id], follower_count=followers[person.id])
    await s.commit()


async def _make_posts(
    s: AsyncSession, batch: TestDataBatch, people: list[User], photos: list[MediaAsset], clips: list[MediaAsset],
    rng: random.Random,
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """Returns (post id, author id) for each post, so other demo data can point at them."""
    now = datetime.now(UTC)
    made: list[tuple[uuid.UUID, uuid.UUID]] = []
    post_rows: list[dict[str, Any]] = []
    media_rows: list[dict[str, Any]] = []
    like_rows: list[dict[str, Any]] = []
    comment_rows: list[dict[str, Any]] = []
    tag_rows: list[dict[str, Any]] = []
    tag_counts: Counter[str] = Counter()
    authored: Counter[uuid.UUID] = Counter()
    for i in range(DEMO_POSTS):
        when = now - timedelta(seconds=rng.randint(60, DAYS_BACK * 86400))
        author = rng.choice(people)
        asset = clips[i % len(clips)] if i < DEMO_REELS + DEMO_VIDEO_POSTS else rng.choice(photos)
        caption = _caption(rng)
        post_id = _id_at(when)
        made.append((post_id, author.id))
        fans = [f for f in rng.sample(people, min(rng.randint(0, 12), len(people))) if f.id != author.id]
        commenters = fans[:rng.choice((0, 0, 1, 1, 2, 3))]
        views = len(fans) * rng.randint(3, 30) + rng.randint(0, 50)
        post_rows.append({
            "id": post_id, "author_id": author.id, "caption": caption, "location": rng.choice(PLACES), "visibility": "public",
            "status": "published", "is_reel": i < DEMO_REELS, "is_capsule": False, "like_count": len(fans),
            "comment_count": len(commenters), "view_count": views, "save_count": 0,
            "engagement_score": len(fans) + 2 * len(commenters) + 0.05 * views, "created_at": when,
        })
        overlay = {**OVERLAY, "text": rng.choice(LINES)} if i % 100 == 0 else None
        media_rows.append({"post_id": post_id, "asset_id": asset.id, "position": 0, "text_overlay": overlay})
        like_rows += [{"user_id": f.id, "post_id": post_id, "created_at": when} for f in fans]
        first_comment: uuid.UUID | None = None
        for n, fan in enumerate(commenters):  # the second comment on a post is a reply to the first
            comment_id = _id_at(when)
            comment_rows.append({
                "id": comment_id, "post_id": post_id, "author_id": fan.id, "parent_id": first_comment if n == 1 else None,
                "body": rng.choice(COMMENTS), "reply_count": 1 if n == 0 and len(commenters) > 1 else 0, "held": False,
                "created_at": when + timedelta(minutes=5),
            })
            first_comment = first_comment or comment_id
        for tag in extract_hashtags(caption):
            tag_rows.append({"tag": tag, "post_id": post_id})
            tag_counts[tag] += 1
        authored[author.id] += 1

    for tag, count in tag_counts.items():
        stmt = insert(Hashtag).values(tag=tag, post_count=count)
        await s.execute(stmt.on_conflict_do_update(index_elements=["tag"], set_={"post_count": Hashtag.post_count + count}))
    await s.commit()
    for start in range(0, len(post_rows), CHUNK):
        await s.execute(insert(Post), post_rows[start:start + CHUNK])
        await s.execute(insert(PostMedia), media_rows[start:start + CHUNK])
        batch.post_count = min(start + CHUNK, len(post_rows))
        await s.commit()
    await _insert(s, PostHashtag, tag_rows)
    await _insert(s, Like, like_rows)
    await _insert(s, Comment, comment_rows)
    for person_id, count in authored.items():
        await users.bump_counts(s, person_id, post_count=count)
    await s.commit()
    return made


def _sticker(i: int) -> dict[str, Any] | None:
    if i % 5 == 0:
        return {"kind": "poll", "question": "Beach or mountains?", "options": ["Beach", "Mountains"], "correct": None}
    if i % 5 == 1:
        return {"kind": "quiz", "question": "Which city is on the coast?", "options": ["Jaipur", "Kochi", "Pune"], "correct": 1}
    return None


async def _make_stories(
    s: AsyncSession, people: list[User], real: list[User], photos: list[MediaAsset], rng: random.Random
) -> None:
    now = datetime.now(UTC)
    stories: list[dict[str, Any]] = []
    views: list[dict[str, Any]] = []
    reactions: list[dict[str, Any]] = []
    answers: list[dict[str, Any]] = []
    for i in range(DEMO_STORIES):
        asset = rng.choice(photos)
        author = rng.choice(people)
        story_id, sticker = _id_at(now), _sticker(i)
        viewers = [p for p in rng.sample(people, min(5, len(people))) if p.id != author.id]
        stories.append({
            "id": story_id, "author_id": author.id, "asset_id": asset.id, "media_key": asset.raw_key,
            "expires_at": now + timedelta(hours=24), "view_count": len(viewers),
            "audience": "close_friends" if i % 10 == 9 else "everyone",
            "frame": ("diwali", "holi", "eid", "christmas")[i % 4] if i % 7 == 0 else None, "sticker": sticker,
        })
        views += [{"story_id": story_id, "viewer_id": p.id} for p in viewers]
        reactions += [{"story_id": story_id, "user_id": p.id, "emoji": "🔥"} for p in viewers[:2]]
        if sticker:
            answers += [{"story_id": story_id, "user_id": p.id, "option": rng.randrange(2)} for p in viewers]
    await _insert(s, Story, stories)
    await _insert(s, StoryView, views)
    await _insert(s, StoryReaction, reactions)
    await _insert(s, StoryAnswer, answers)
    await _insert(s, CloseFriend, [{"user_id": a.id, "friend_id": r.id} for a in people for r in real])
    shelves = stories[:10]
    highlights = [{"id": _id_at(now), "user_id": row["author_id"], "title": "Best of the year"} for row in shelves]
    await _insert(s, Highlight, highlights)
    links = [{"highlight_id": h["id"], "story_id": row["id"]} for h, row in zip(highlights, shelves, strict=True)]
    await _insert(s, HighlightStory, links)


async def _make_post_extras(
    s: AsyncSession, people: list[User], made: list[tuple[uuid.UUID, uuid.UUID]], rng: random.Random
) -> None:
    """Tags, collabs, saves, pins, verified and private accounts."""
    sample = rng.sample(made, min(1000, len(made)))
    others = {p.id: [o.id for o in people if o.id != p.id] for p in people}
    await _insert(s, PostTag, [{"post_id": post, "user_id": rng.choice(others[author])} for post, author in sample[:300]])
    await _insert(s, PostCollab, [
        {"post_id": post, "user_id": rng.choice(others[author]), "status": "accepted"} for post, author in sample[300:350]
    ])
    savers = people[:5]
    saves = [post for post, _ in sample[350:450]]
    await _insert(s, Save, [{"user_id": p.id, "post_id": post} for p in savers for post in saves])
    await s.execute(update(Post).where(Post.id.in_(saves)).values(save_count=Post.save_count + len(savers)))
    first_post = {author: post for post, author in reversed(sample)}
    await s.execute(update(Post).where(Post.id.in_(list(first_post.values())[:10])).values(pinned_at=datetime.now(UTC)))
    await s.execute(update(User).where(User.id.in_([p.id for p in people[:5]])).values(verified=True))
    private = [p.id for p in people[len(people) - len(people) // 20:]]
    await s.execute(update(User).where(User.id.in_(private)).values(is_private=True))
    await s.commit()


async def _make_communities(
    s: AsyncSession, people: list[User], real: list[User], photos: list[MediaAsset], rng: random.Random
) -> None:
    names = ["Travel India", "Street Food Lovers", "Monsoon Photographers", "Weekend Riders", "Home Cooks", "Mountain Trekkers"]
    communities = [
        {"id": uuid.uuid4(), "slug": f"demo-{secrets.token_hex(4)}", "name": name, "description": f"{name}: a demo community.",
         "owner_id": rng.choice(people).id}
        for name in names
    ]
    await _insert(s, Community, communities)
    members: list[dict[str, Any]] = []
    posts: list[dict[str, Any]] = []
    for community in communities:
        joined = {p.id for p in rng.sample(people, min(25, len(people)))} | {community["owner_id"]} | {r.id for r in real}
        members += [{"community_id": community["id"], "user_id": user_id} for user_id in joined]
        authors = [p for p in people if p.id in joined]
        posts += [
            {"community_id": community["id"], "author_id": rng.choice(authors).id, "body": rng.choice(LINES),
             "asset_id": rng.choice(photos).id if n % 2 else None}
            for n in range(10)
        ]
    await _insert(s, CommunityMember, members)
    await _insert(s, CommunityPost, posts)


async def _make_staff_queues(
    s: AsyncSession, people: list[User], made: list[tuple[uuid.UUID, uuid.UUID]], rng: random.Random
) -> None:
    """Reports, support tickets, verification and ad requests, so every admin screen has work in it."""
    reasons = ["spam", "harassment", "misinformation", "nudity", "violence"]
    posts = rng.sample(made, min(40, len(made)))
    reports: list[dict[str, Any]] = [
        {"reporter_id": rng.choice(people).id, "entity_type": "post", "entity_id": post, "reason": reasons[n % len(reasons)],
         "details": "Reported for demo testing.", "status": "open", "source": "user", "score": None}
        for n, (post, _) in enumerate(posts[:25])
    ]
    reports += [
        {"reporter_id": None, "entity_type": "post", "entity_id": post, "reason": reasons[n % len(reasons)],
         "details": None, "status": "open", "source": "ai", "score": 0.8}
        for n, (post, _) in enumerate(posts[25:30])
    ]
    reports += [
        {"reporter_id": rng.choice(people).id, "entity_type": "user", "entity_id": p.id, "reason": "spam",
         "details": "Reported for demo testing.", "status": "open", "source": "user", "score": None}
        for p in people[:5]
    ]
    await _insert(s, Report, reports)
    subjects = ["Cannot upload my video", "How do I change my username?", "Someone copied my photos", "Login code never arrived"]
    tickets = [
        {"id": uuid.uuid4(), "user_id": rng.choice(people).id, "subject": subjects[n % len(subjects)],
         "status": ("open", "open", "escalated", "resolved")[n % 4]}
        for n in range(16)
    ]
    await _insert(s, Ticket, tickets)
    await _insert(s, TicketMessage, [
        {"ticket_id": t["id"], "author_id": t["user_id"], "is_staff": False, "body": "Please help me with this."} for t in tickets
    ])
    await _insert(s, VerificationRequest, [
        {"user_id": p.id, "kind": "business" if n % 2 else "person", "details": "Demo request.", "status": "pending"}
        for n, p in enumerate(people[5:15])
    ])
    await _insert(s, AdRequest, [
        {"business_id": author, "post_id": post, "headline": rng.choice(LINES)[:80], "city": rng.choice(PLACES),
         "daily_budget_paise": 50_000, "status": "pending"}
        for post, author in posts[30:40]
    ])


async def _link_real_accounts(
    s: AsyncSession, people: list[User], real: list[User], made: list[tuple[uuid.UUID, uuid.UUID]], rng: random.Random
) -> None:
    """Test accounts cannot log in, so the accounts you can log in with need a feed, chats and notifications."""
    now = datetime.now(UTC)
    public = [p for p in people[: len(people) - len(people) // 20]]
    conversations: list[dict[str, Any]] = []
    members: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = []
    notes: list[dict[str, Any]] = []
    follows: list[dict[str, Any]] = []
    for person in real:
        following = rng.sample(public, min(30, len(public)))
        fans = rng.sample(public, min(13, len(public)))
        follows += [{"follower_id": person.id, "followee_id": p.id, "status": "active"} for p in following]
        follows += [{"follower_id": p.id, "followee_id": person.id, "status": "active"} for p in fans[:10]]
        follows += [{"follower_id": p.id, "followee_id": person.id, "status": "pending"} for p in fans[10:]]
        await users.bump_counts(s, person.id, following_count=len(following), follower_count=len(fans[:10]))
        for p in following:
            await users.bump_counts(s, p.id, follower_count=1)
        for p in fans[:10]:
            await users.bump_counts(s, p.id, following_count=1)
        chats = [[p] for p in rng.sample(public, min(5, len(public)))] + [rng.sample(public, min(4, len(public)))]
        for n, others in enumerate(chats):
            conv = uuid.uuid4()
            is_group = n == len(chats) - 1
            conversations.append({
                "id": conv, "is_group": is_group, "title": "Weekend trip plan" if is_group else None, "created_by": others[0].id,
                "direct_key": None if is_group else ":".join(sorted([person.id.hex, others[0].id.hex]))[:80],
                "last_message_at": now,
            })
            members.append({"conversation_id": conv, "user_id": person.id, "state": "request" if n == 0 else "active"})
            members += [{"conversation_id": conv, "user_id": p.id, "state": "active"} for p in others]
            for m, body in enumerate(("Hi! Saw your latest post.", "Thanks, it was a fun day.", "Where was it taken?")):
                sender = person.id if m == 1 and n != 0 else others[0].id
                messages.append({
                    "conversation_id": conv, "sender_id": sender, "body": body,
                    "post_id": made[n][0] if m == 2 else None, "created_at": now - timedelta(minutes=30 - m),
                })
        kinds = ("like", "comment", "follow", "tagged", "mention", "message")
        notes += [
            {"user_id": person.id, "type": kinds[n % len(kinds)], "actor_id": rng.choice(public).id,
             "entity_id": made[n % len(made)][0]}
            for n in range(30)
        ]
    await _insert(s, Follow, follows)
    await _insert(s, Conversation, conversations)
    await _insert(s, ConversationMember, members)
    await _insert(s, Message, messages)
    await _insert(s, Notification, notes)
    await s.commit()
    for person in real:
        await invalidate_feed(person.id)


async def create(s: AsyncSession, batch: TestDataBatch) -> None:
    started = time.monotonic()
    rng = random.Random(batch.id.int)  # noqa: S311
    people = await _make_people(s, batch, DEMO_USERS, rng)
    photos, clips = await _make_library(s, people[0])
    await _make_follows(s, people, rng)
    made = await _make_posts(s, batch, people, photos, clips, rng)
    real = await users.by_usernames(s, list(REAL_ACCOUNTS)) if REAL_ACCOUNTS else []
    await _make_stories(s, people, real, photos, rng)
    await _make_post_extras(s, people, made, rng)
    await _make_communities(s, people, real, photos, rng)
    await _make_staff_queues(s, people, made, rng)
    await _link_real_accounts(s, people, real, made, rng)
    log.info("demo_batch_ready", seconds=round(time.monotonic() - started), photos=len(photos), clips=len(clips))
