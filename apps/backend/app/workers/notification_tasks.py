import asyncio
import json
import uuid
from email.message import EmailMessage

import aiosmtplib
import structlog
from pywebpush import WebPushException, webpush

from app import models  # noqa: F401
from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.follows import repository as follows
from app.modules.notifications import repository as repo
from app.modules.notifications.service import notify
from app.modules.users import repository as users
from app.workers.celery_app import celery
from app.workers.runtime import run

log = structlog.get_logger()


async def _send_email(to: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = settings.mail_from, to, subject
    message.set_content(body)
    await aiosmtplib.send(
        message, hostname=settings.smtp_host, port=settings.smtp_port, start_tls=settings.smtp_tls,
        username=settings.smtp_user or None, password=settings.smtp_password or None,
    )


@celery.task(name="notifications.send_email", bind=True, max_retries=5, default_retry_delay=30)
def send_email(self, to: str, subject: str, body: str) -> None:  # type: ignore[no-untyped-def]
    try:
        run(_send_email(to, subject, body))
    except (aiosmtplib.SMTPException, OSError) as exc:
        raise self.retry(exc=exc) from exc


async def _push(user_id: uuid.UUID, title: str, url: str) -> None:
    if not settings.vapid_private_key:
        return
    async with SessionLocal() as s:
        targets = await repo.push_targets(s, user_id)
        for target in targets:
            try:
                await asyncio.to_thread(
                    webpush,
                    subscription_info={"endpoint": target.endpoint, "keys": {"p256dh": target.p256dh, "auth": target.auth}},
                    data=json.dumps({"title": "RedStarVibe", "body": title, "url": url}),
                    vapid_private_key=settings.vapid_private_key,
                    vapid_claims={"sub": settings.vapid_subject},
                    timeout=10,
                )
            except WebPushException as exc:
                status = exc.response.status_code if exc.response is not None else None
                if status in {404, 410}:  # the browser unsubscribed
                    await repo.delete_push_by_endpoint(s, target.endpoint)
                else:
                    log.warning("web_push_failed", status=status)
        await s.commit()


@celery.task(name="notifications.web_push")
def web_push(user_id: str, title: str, url: str) -> None:
    run(_push(uuid.UUID(user_id), title, url))


@celery.task(name="notifications.push_call")
def push_call(user_id: str, caller: str, room: str) -> None:
    run(_push(uuid.UUID(user_id), f"{caller} is calling you", f"/call/{room}"))


async def _live_started(host_id: uuid.UUID, room: str) -> None:
    async with SessionLocal() as s:
        for follower in (await follows.active_follower_ids(s, host_id))[:1000]:
            await notify(s, follower, "live", host_id)
        _ = room


@celery.task(name="notifications.live_started")
def live_started(host_id: str, room: str) -> None:
    run(_live_started(uuid.UUID(host_id), room))


async def _score_spam(user_id: uuid.UUID, follows_per_hour: float = 0.0) -> None:
    from sqlalchemy import select

    from app.ai.safety.spam import REVIEW_THRESHOLD, spam_score
    from app.modules.moderation.models import Report

    async with SessionLocal() as s:
        user = await users.by_id(s, user_id)
        if user is None:
            return
        user.spam_score = spam_score(user.username, user.email, user.profile.bio, follows_per_hour)
        if user.spam_score >= REVIEW_THRESHOLD:
            open_report = select(Report.id).where(Report.entity_id == user.id, Report.source == "ai", Report.status == "open")
            if (await s.execute(open_report)).first() is None:
                s.add(Report(entity_type="user", entity_id=user.id, reason="spam_signals", source="ai", score=user.spam_score))
        await s.commit()


@celery.task(name="users.score_spam")
def score_spam(user_id: str, follows_per_hour: str = "0") -> None:
    run(_score_spam(uuid.UUID(user_id), float(follows_per_hour)))
