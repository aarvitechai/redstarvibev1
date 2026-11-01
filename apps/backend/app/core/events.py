"""Domain events. Emitted after commit; workers react (notifications, counters, fan-out, AI)."""
import asyncio
from typing import Any

from app.workers.celery_app import celery


async def emit(name: str, **payload: Any) -> None:
    data = {k: str(v) if v is not None else None for k, v in payload.items()}
    await asyncio.to_thread(celery.send_task, "events.dispatch", args=[name, data], queue="default")


async def enqueue(task: str, *args: Any, queue: str = "default") -> None:
    await asyncio.to_thread(celery.send_task, task, args=[str(a) for a in args], queue=queue)
