import re
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import counter_incr
from app.core.errors import bad_request, forbidden, not_found
from app.core.events import emit
from app.core.pagination import Page, encode_cursor
from app.core.rate_limit import hit
from app.modules.comments import repository as repo
from app.modules.comments.models import Comment
from app.modules.comments.schemas import CommentIn, CommentOut
from app.modules.posts import repository as post_repo
from app.modules.posts import service as posts
from app.modules.users import repository as users
from app.modules.users import service as user_service
from app.modules.users.models import User


def has_hidden_word(body: str, words: list[str]) -> bool:
    """Whole words only, so hiding "spam" does not catch "spamming"."""
    return any(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", body, re.IGNORECASE) for word in words)


async def _should_hold(s: AsyncSession, author: User, post_author: User, body: str) -> bool:
    if author.id == post_author.id:
        return False
    if await users.has_limit(s, post_author.id, author.id, "restrict"):
        return True
    return has_hidden_word(body, post_author.profile.hidden_words or [])


async def _announce(s: AsyncSession, viewer: User, comment: Comment, post_author: uuid.UUID) -> None:
    await counter_incr(comment.post_id, "comment_count", 1)
    await emit(
        "comment.created", comment_id=comment.id, post_id=comment.post_id, actor_id=comment.author_id, author_id=post_author
    )
    fresh = (await posts.hydrate(s, viewer, [comment.post_id]))[0]
    await posts._publish_count(comment.post_id, "comment_count", fresh.comment_count)


def _out(comment: Comment, viewer: User | None, post_author: uuid.UUID) -> CommentOut:
    can_delete = bool(viewer and viewer.id in {comment.author_id, post_author})
    return CommentOut(
        id=comment.id, post_id=comment.post_id, parent_id=comment.parent_id, author=user_service.brief(comment.author),
        body=comment.body, reply_count=comment.reply_count, held=comment.held, created_at=comment.created_at,
        can_delete=can_delete,
    )


async def create(s: AsyncSession, user: User, post_id: uuid.UUID, data: CommentIn) -> CommentOut:
    await hit(f"comment:user:{user.id}", 60, 3600)
    post = await posts.get_viewable(s, user, post_id)
    body = data.body.strip()
    if not body:
        raise bad_request("empty_comment", "Write something first")
    held = await _should_hold(s, user, post.author, body)
    parent_id = None
    if data.parent_id:
        parent = await repo.get(s, data.parent_id)
        if parent is None or parent.post_id != post.id:
            raise not_found("Comment")
        parent_id = parent.parent_id or parent.id  # replies stay one level deep
        if not held:
            await repo.bump_replies(s, parent_id, 1)
    comment = Comment(post_id=post.id, author_id=user.id, parent_id=parent_id, body=body, held=held)
    await repo.add(s, comment)
    await s.commit()
    if not held:
        await _announce(s, user, comment, post.author_id)
    comment.author = user
    return _out(comment, user, post.author_id)


async def list_comments(
    s: AsyncSession, viewer: User | None, post_id: uuid.UUID, parent_id: uuid.UUID | None,
    cursor: uuid.UUID | None, limit: int,
) -> Page[CommentOut]:
    post = await posts.get_viewable(s, viewer, post_id)
    hidden = await users.blocked_ids(s, viewer.id) if viewer else set()
    viewer_id = viewer.id if viewer else None
    rows = await repo.list_for_post(s, post.id, parent_id, cursor, limit + 1, hidden, viewer_id, post.author_id)
    more = len(rows) > limit
    rows = rows[:limit]
    return Page(
        items=[_out(c, viewer, post.author_id) for c in rows],
        next_cursor=encode_cursor(rows[-1].id) if more else None,
    )


async def delete(s: AsyncSession, user: User, comment_id: uuid.UUID) -> None:
    comment = await repo.get(s, comment_id)
    if comment is None:
        raise not_found("Comment")
    post = await post_repo.get(s, comment.post_id)
    if user.id != comment.author_id and (post is None or post.author_id != user.id):
        raise forbidden("You cannot delete this comment")
    comment.deleted_at = datetime.now(UTC)
    if comment.parent_id and not comment.held:
        await repo.bump_replies(s, comment.parent_id, -1)
    await s.commit()
    if not comment.held:
        await counter_incr(comment.post_id, "comment_count", -1)


async def approve(s: AsyncSession, user: User, comment_id: uuid.UUID) -> None:
    """The post owner shows a held comment to everyone."""
    comment = await repo.get(s, comment_id)
    if comment is None:
        raise not_found("Comment")
    post = await post_repo.get(s, comment.post_id)
    if post is None or post.author_id != user.id:
        raise forbidden("Only the post owner can approve this comment")
    if not comment.held:
        return
    comment.held = False
    if comment.parent_id:
        await repo.bump_replies(s, comment.parent_id, 1)
    await s.commit()
    await _announce(s, user, comment, post.author_id)
