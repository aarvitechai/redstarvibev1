from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import not_found
from app.core.rate_limit import hit
from app.modules.chat import repository as chat
from app.modules.comments import repository as comments
from app.modules.moderation import repository as repo
from app.modules.moderation.models import Report
from app.modules.moderation.schemas import ReportIn, ReportOut
from app.modules.posts import service as posts
from app.modules.stories import repository as stories
from app.modules.users import repository as users
from app.modules.users import service as user_service
from app.modules.users.models import User


def out(r: Report) -> ReportOut:
    return ReportOut(
        id=r.id, entity_type=r.entity_type, entity_id=r.entity_id, reason=r.reason, details=r.details,
        status=r.status, source=r.source, score=r.score, created_at=r.created_at,
    )


async def _check_reportable(s: AsyncSession, me: User, data: ReportIn) -> None:
    """You can only report what you can see."""
    if data.entity_type == "post":
        await posts.get_viewable(s, me, data.entity_id)
    elif data.entity_type == "comment":
        comment = await comments.get(s, data.entity_id)
        if comment is None:
            raise not_found("Comment")
        await posts.get_viewable(s, me, comment.post_id)
    elif data.entity_type == "user":
        if await users.by_id(s, data.entity_id) is None:
            raise not_found("User")
    elif data.entity_type == "story":
        story = await stories.get(s, data.entity_id)
        if story is None or not await user_service.can_view_content_of(s, me, story.author):
            raise not_found("Story")
    elif data.entity_type == "message":
        from sqlalchemy import select

        from app.modules.chat.models import Message

        row = (await s.execute(select(Message.conversation_id).where(Message.id == data.entity_id))).first()
        if row is None or me.id not in await chat.member_ids(s, row[0]):
            raise not_found("Message")


async def create_report(s: AsyncSession, me: User, data: ReportIn) -> ReportOut:
    await hit(f"report:user:{me.id}", 30, 3600)
    await _check_reportable(s, me, data)
    report = Report(
        reporter_id=me.id, entity_type=data.entity_type, entity_id=data.entity_id, reason=data.reason, details=data.details,
    )
    await repo.add(s, report)
    await s.commit()
    return out(report)
