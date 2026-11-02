"""Event driven side effects. One dispatcher so new reactions never change the emitting module."""
import uuid

import structlog

from app import models  # noqa: F401
from app.ai.rag.ingest import delete_entity, upsert_entity
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.events import enqueue
from app.modules.chat import repository as chat
from app.modules.comments import repository as comments
from app.modules.feed import service as feed
from app.modules.follows import repository as follows
from app.modules.notifications.service import notify
from app.modules.posts import repository as post_repo
from app.modules.posts.service import extract_mentions
from app.modules.users import repository as users
from app.workers.celery_app import celery
from app.workers.runtime import run

log = structlog.get_logger()
NEW_POST_NOTIFY_LIMIT = 1000


def _u(value: str | None) -> uuid.UUID | None:
    return uuid.UUID(value) if value else None


async def _dispatch(name: str, d: dict[str, str]) -> None:
    async with SessionLocal() as s:
        if name == "post.published":
            post = await post_repo.get(s, uuid.UUID(d["post_id"]))
            if post is None:
                return
            author = post.author
            followers = await follows.active_follower_ids(s, post.author_id)
            if author.follower_count < settings.celebrity_threshold:
                await feed.fan_out(post.id, followers + [post.author_id])
                if len(followers) <= NEW_POST_NOTIFY_LIMIT:
                    for follower in followers:
                        await notify(s, follower, "new_post", post.author_id, post.id)
            else:
                await feed.fan_out(post.id, [post.author_id])
            await notify(s, post.author_id, "post_published", None, post.id)
            await enqueue("ai.index_post", post.id, queue="ai")
            for user in await users.by_usernames(s, extract_mentions(post.caption)):
                if not await users.is_blocked_either_way(s, post.author_id, user.id):
                    await notify(s, user.id, "mention", post.author_id, post.id)
            for user in post.tagged:
                await notify(s, user.id, "tagged", post.author_id, post.id)
            if post.collab and post.collab.status == "pending":
                await notify(s, post.collab.user_id, "collab_invite", post.author_id, post.id)
        elif name == "post.updated":
            await enqueue("ai.index_post", d["post_id"], queue="ai")
        elif name == "post.collab_accepted":
            post = await post_repo.get(s, uuid.UUID(d["post_id"]))
            partner = uuid.UUID(d["user_id"])
            if post:
                await feed.fan_out(post.id, [*await follows.active_follower_ids(s, partner), partner])
                await notify(s, post.author_id, "collab_accepted", partner, post.id)
        elif name == "post.deleted":
            post_id = uuid.UUID(d["post_id"])
            author_id = uuid.UUID(d["author_id"])
            await feed.remove_from_feeds(post_id, [*await follows.active_follower_ids(s, author_id), author_id])
            await delete_entity(s, "post", str(post_id))
            await delete_entity(s, "own_post", str(post_id))
            await s.commit()
        elif name == "post.liked":
            await notify(s, uuid.UUID(d["author_id"]), "like", _u(d["actor_id"]), _u(d["post_id"]))
        elif name == "comment.created":
            comment = await comments.get(s, uuid.UUID(d["comment_id"]))
            await notify(s, uuid.UUID(d["author_id"]), "comment", _u(d["actor_id"]), _u(d["post_id"]))
            if comment:
                for user in await users.by_usernames(s, extract_mentions(comment.body)):
                    if not await users.is_blocked_either_way(s, comment.author_id, user.id):
                        await notify(s, user.id, "mention", comment.author_id, comment.post_id)
                await upsert_entity(s, "own_comment", str(comment.id), comment.author_id, "Your comment", comment.body)
                await s.commit()
        elif name == "user.followed":
            follower, followee = uuid.UUID(d["follower_id"]), uuid.UUID(d["followee_id"])
            active = d["status"] == "active"
            if active:
                await feed.invalidate_feed(follower)
            await notify(s, followee, "follow" if active else "follow_request", follower)
        elif name == "user.follow_accepted":
            follower, followee = uuid.UUID(d["follower_id"]), uuid.UUID(d["followee_id"])
            await feed.invalidate_feed(follower)
            await notify(s, follower, "follow_accepted", followee)
        elif name == "user.unfollowed":
            await feed.invalidate_feed(uuid.UUID(d["follower_id"]))
        elif name == "message.created":
            sender = uuid.UUID(d["sender_id"])
            conv = uuid.UUID(d["conversation_id"])
            for member, state in (await chat.member_states(s, conv)).items():
                if member != sender and state != "declined":
                    await notify(s, member, "message_request" if state == "request" else "message", sender, conv)


@celery.task(name="events.dispatch", max_retries=3, default_retry_delay=10, bind=True)
def dispatch(self, name: str, payload: dict[str, str]) -> None:  # type: ignore[no-untyped-def]
    try:
        run(_dispatch(name, payload))
    except Exception as exc:
        log.exception("event_failed", event=name)
        raise self.retry(exc=exc) from exc
