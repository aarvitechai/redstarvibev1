"""The full report list: every status, filters, a preview of what was reported, and CSV export."""
import csv
import io
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, encode_cursor
from app.modules.comments import repository as comments
from app.modules.communities.service import get_post_for_report
from app.modules.media.service import asset_out
from app.modules.moderation.models import Report
from app.modules.moderation.schemas import ReportOut
from app.modules.moderation.service import out as report_out
from app.modules.posts import repository as posts
from app.modules.stories import repository as stories
from app.modules.users import repository as users

ReportStatus = Literal["open", "actioned", "dismissed", "all"]
EXPORT_LIMIT = 5000


class ReportTarget(BaseModel):
    available: bool
    author: str | None = None
    text: str | None = None
    thumbnail: str | None = None
    link: str | None = None


class AdminReport(ReportOut):
    reporter: str | None
    resolved_by_name: str | None
    resolved_at: datetime | None
    escalated_by_name: str | None
    target: ReportTarget


class ReportCounts(BaseModel):
    open: int = 0
    actioned: int = 0
    dismissed: int = 0


def _filtered(status: str, entity_type: str | None, source: str | None, reason: str | None):  # type: ignore[no-untyped-def]
    q = select(Report)
    if status != "all":
        q = q.where(Report.status == status)
    if entity_type:
        q = q.where(Report.entity_type == entity_type)
    if source:
        q = q.where(Report.source == source)
    if reason:
        q = q.where(Report.reason == reason)
    return q


async def _target(s: AsyncSession, report: Report) -> ReportTarget:
    gone = ReportTarget(available=False)
    if report.entity_type == "post":
        post = await posts.get(s, report.entity_id)
        if post is None:
            return gone
        asset = asset_out(post.media[0].asset) if post.media else None
        thumbnail = None
        if asset:
            thumbnail = asset.images[0].webp if asset.images else asset.poster
        return ReportTarget(
            available=True, author=post.author.username, text=post.full_text[:300], thumbnail=thumbnail, link=f"/p/{post.id}",
        )
    if report.entity_type == "comment":
        comment = await comments.get(s, report.entity_id)
        if comment is None:
            return gone
        return ReportTarget(
            available=True, author=comment.author.username, text=comment.body[:300], link=f"/p/{comment.post_id}",
        )
    if report.entity_type == "user":
        user = await users.by_id(s, report.entity_id)
        if user is None:
            return gone
        return ReportTarget(available=True, author=user.username, text=user.profile.bio[:300], link=f"/{user.username}")
    if report.entity_type == "story":
        story = await stories.get(s, report.entity_id)
        if story is None:
            return gone
        asset = asset_out(story.asset)
        thumbnail = asset.images[0].webp if asset.images else asset.poster
        return ReportTarget(available=True, author=story.author.username, thumbnail=thumbnail)
    if report.entity_type == "community":
        community_post = await get_post_for_report(s, report.entity_id)
        if community_post is None:
            return gone
        return ReportTarget(available=True, author=community_post.author.username, text=community_post.body[:300])
    return ReportTarget(available=True, text="Private message. The content is not shown to staff here.")


async def _admin_out(s: AsyncSession, report: Report, names: dict[uuid.UUID, str]) -> AdminReport:
    return AdminReport(
        **report_out(report).model_dump(),
        reporter=names.get(report.reporter_id) if report.reporter_id else None,
        resolved_by_name=names.get(report.resolved_by) if report.resolved_by else None,
        resolved_at=report.resolved_at,
        escalated_by_name=names.get(report.escalated_by) if report.escalated_by else None,
        target=await _target(s, report),
    )


async def _names(s: AsyncSession, rows: list[Report]) -> dict[uuid.UUID, str]:
    ids = {i for r in rows for i in (r.reporter_id, r.resolved_by, r.escalated_by) if i}
    return {uid: u.username for uid, u in (await users.by_ids(s, list(ids))).items()}


async def page(
    s: AsyncSession, status: ReportStatus, entity_type: str | None, source: str | None, reason: str | None,
    cursor: uuid.UUID | None, limit: int,
) -> Page[AdminReport]:
    q = _filtered(status, entity_type, source, reason)
    if status == "open":  # the queue is first come, first served; history is newest first
        q = q.where(Report.id > cursor) if cursor else q
        q = q.order_by(Report.id.asc())
    else:
        q = q.where(Report.id < cursor) if cursor else q
        q = q.order_by(Report.id.desc())
    rows = list((await s.execute(q.limit(limit + 1))).scalars())
    more = len(rows) > limit
    rows = rows[:limit]
    names = await _names(s, rows)
    return Page(
        items=[await _admin_out(s, r, names) for r in rows],
        next_cursor=encode_cursor(rows[-1].id) if more else None,
    )


async def counts(s: AsyncSession) -> ReportCounts:
    rows = await s.execute(select(Report.status, func.count()).group_by(Report.status))
    return ReportCounts(**{r[0]: r[1] for r in rows if r[0] in ReportCounts.model_fields})


def csv_safe(value: object) -> str:
    """Spreadsheets run cells that start with these characters as formulas, and report text comes from users."""
    text = "" if value is None else str(value)
    return f"'{text}" if text[:1] in {"=", "+", "-", "@", "\t", "\r"} else text


async def export_csv(
    s: AsyncSession, status: ReportStatus, entity_type: str | None, source: str | None, reason: str | None
) -> str:
    q = _filtered(status, entity_type, source, reason).order_by(Report.id.desc()).limit(EXPORT_LIMIT)
    rows = list((await s.execute(q)).scalars())
    names = await _names(s, rows)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["id", "created_at", "status", "type", "target_id", "reason", "details", "source", "score", "reporter",
                     "resolved_by", "resolved_at"])
    for r in rows:
        writer.writerow([csv_safe(v) for v in (
            r.id, r.created_at.isoformat(), r.status, r.entity_type, r.entity_id, r.reason, r.details, r.source, r.score,
            names.get(r.reporter_id) if r.reporter_id else None, names.get(r.resolved_by) if r.resolved_by else None,
            r.resolved_at.isoformat() if r.resolved_at else None,
        )])
    return out.getvalue()
