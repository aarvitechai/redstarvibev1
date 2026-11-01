import uuid

from app import models  # noqa: F401
from app.modules.admin import test_data
from app.workers.celery_app import celery
from app.workers.runtime import run


@celery.task(name="admin.create_test_batch", time_limit=3600)
def create_test_batch(batch_id: str) -> None:
    run(test_data.create_batch(uuid.UUID(batch_id)))


@celery.task(name="admin.remove_test_batch", time_limit=3600)
def remove_test_batch(batch_id: str) -> None:
    run(test_data.remove_batch(uuid.UUID(batch_id)))
