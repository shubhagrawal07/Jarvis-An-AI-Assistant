"""Celery tasks: reminders, calendar, FCM sweeps."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import redis
from sqlalchemy import and_, select

from app.config import get_settings
from app.db.models import DayRecord, Task, TaskStatus, User
from app.db.session import AsyncSessionLocal
from app.db.sync_session import get_sync_session
from app.integrations import fcm
from app.integrations.google_calendar import delete_event, upsert_event_for_task
from app.services import task_service
from app.utils.timezone import get_zone, local_day_bounds_utc, utc_now

from app.workers.celery_app import celery_app

_redis: redis.Redis | None = None


def _r() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


def _priority_key(p: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(p.lower(), 3)


@celery_app.task(name="app.workers.tasks.send_task_reminder")
def send_task_reminder(task_id: str) -> None:
    with get_sync_session() as session:
        t = session.get(Task, UUID(task_id))
        if not t or t.status != TaskStatus.PENDING.value:
            return
        user = session.get(User, t.user_id)
        if not user or not user.fcm_token:
            return
        fcm.send_push(
            user.fcm_token,
            "Task reminder",
            t.title,
            data={"type": "reminder", "task_id": task_id},
        )


@celery_app.task(name="app.workers.tasks.sync_calendar_task")
def sync_calendar_task(task_id: str) -> None:
    tid = UUID(task_id)
    with get_sync_session() as session:
        t = session.get(Task, tid)
        if not t:
            return
        uid = t.user_id
    upsert_event_for_task(uid, tid)


@celery_app.task(name="app.workers.tasks.delete_calendar_event_task")
def delete_calendar_event_task(google_event_id: str, user_id: str) -> None:
    delete_event(UUID(user_id), google_event_id)


@celery_app.task(name="app.workers.tasks.sweep_user_notifications")
def sweep_user_notifications() -> None:
    asyncio.run(_sweep_async())


async def _sweep_async() -> None:
    now = utc_now()
    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(User))).scalars().all()

    for user in users:
        try:
            async with AsyncSessionLocal() as session:
                u = await session.get(User, user.id)
                if u:
                    await _maybe_morning_async(session, u, now)
                    await session.commit()
        except Exception:
            pass
        try:
            async with AsyncSessionLocal() as session:
                u = await session.get(User, user.id)
                if u:
                    await _maybe_eod_async(session, u, now)
                    await session.commit()
        except Exception:
            pass
        try:
            async with AsyncSessionLocal() as session:
                u = await session.get(User, user.id)
                if u:
                    await _maybe_autoclose_async(session, u, now)
                    await session.commit()
        except Exception:
            pass


async def _maybe_morning_async(session, user: User, now: datetime) -> None:
    z = get_zone(user.timezone)
    local = now.astimezone(z)
    if local.hour != user.morning_summary_hour or local.minute >= 15:
        return
    today = local.date()
    key = f"morning:{user.id}:{today}"
    if _r().get(key):
        return
    tasks = await task_service.pending_tasks_for_local_date(session, user, today)
    tasks.sort(key=lambda t: (_priority_key(t.priority), t.due_at))
    lines = [f"- {t.title} ({t.priority})" for t in tasks[:12]]
    body = f"You have {len(tasks)} tasks today.\n" + "\n".join(lines)
    if user.fcm_token:
        fcm.send_push(
            user.fcm_token,
            "Today's tasks",
            body[:2000],
            data={"type": "morning_summary"},
        )
    _r().setex(key, 86400, "1")


async def _maybe_eod_async(session, user: User, now: datetime) -> None:
    z = get_zone(user.timezone)
    local = now.astimezone(z)
    if not (user.eod_prompt_start_hour <= local.hour <= user.eod_prompt_end_hour):
        return
    today = local.date()
    key = f"eod:{user.id}:{today}"
    if _r().get(key):
        return
    if user.fcm_token:
        fcm.send_push(
            user.fcm_token,
            "End of day",
            "Did you complete your tasks today?",
            data={"type": "eod_prompt"},
        )
    _r().setex(key, 86400, "1")


async def _maybe_autoclose_async(session, user: User, now: datetime) -> None:
    z = get_zone(user.timezone)
    local = now.astimezone(z)
    settings = get_settings()
    if local.hour != 0 or local.minute > settings.auto_close_grace_minutes_after_midnight:
        return
    yesterday = local.date() - timedelta(days=1)
    r = await session.execute(
        select(DayRecord).where(
            DayRecord.user_id == user.id,
            DayRecord.local_date == yesterday,
        )
    )
    existing = r.scalar_one_or_none()
    if existing and existing.day_closed:
        return
    key = f"autoclose:{user.id}:{yesterday}"
    if _r().get(key):
        return
    await task_service.close_day(session, user, yesterday, notes="auto-close")
    _r().setex(key, 86400, "1")
