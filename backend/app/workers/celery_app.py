"""Celery application."""

from datetime import UTC, datetime

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "jarvis",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.timezone = "UTC"
celery_app.conf.beat_schedule = {
    "sweep-notifications": {
        "task": "app.workers.tasks.sweep_user_notifications",
        "schedule": crontab(minute="*/5"),
    },
}


def schedule_task_reminder(task_id: str, at: datetime) -> None:
    from app.workers.tasks import send_task_reminder

    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    send_task_reminder.apply_async(args=[task_id], eta=at)
