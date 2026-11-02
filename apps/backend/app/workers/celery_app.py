from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery = Celery(
    "redstarvibe",
    broker=settings.celery_broker_url or settings.redis_url,
    include=[
        "app.workers.event_tasks", "app.workers.media_tasks", "app.workers.ai_tasks",
        "app.workers.feed_tasks", "app.workers.notification_tasks", "app.workers.admin_tasks",
    ],
)
celery.conf.update(
    task_default_queue="default",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_ignore_result=True,
    broker_connection_retry_on_startup=True,
    timezone="UTC",
    beat_schedule={
        "flush-counters": {"task": "feed.flush_counters", "schedule": 5.0},
        "publish-scheduled": {"task": "feed.publish_scheduled", "schedule": 30.0},
        "purge-stories": {"task": "feed.purge_stories", "schedule": crontab(minute=7)},
        "purge-accounts": {"task": "feed.purge_accounts", "schedule": crontab(hour=3, minute=17)},
        "ensure-partitions": {"task": "feed.ensure_partitions", "schedule": crontab(day_of_month="1", hour=1, minute=5)},
        "backfill-search": {"task": "ai.backfill_search", "schedule": crontab(hour=2, minute=41)},
        "ingest-help": {"task": "ai.ingest_help", "schedule": crontab(hour=2, minute=11)},
    },
)
