from datetime import date, datetime
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DayRecord, Task, TaskStatus, User
from app.services.inference import merge_inference
from app.utils.timezone import local_day_bounds_utc, utc_now


async def get_user(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)


async def create_task(
    session: AsyncSession,
    user: User,
    *,
    title: str,
    task_type: str | None,
    due_at: datetime,
    priority: str | None = None,
    reminder_at: datetime | None = None,
) -> Task:
    nt, pr, rem, pts, pen = merge_inference(
        title=title,
        task_type=task_type,
        due_at=due_at,
        priority=priority,
        reminder_at=reminder_at,
    )
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=utc_now().tzinfo)
    task = Task(
        user_id=user.id,
        title=title,
        task_type=nt,
        due_at=due_at,
        priority=pr,
        reminder_at=rem,
        points=pts,
        penalty_text=pen,
        status=TaskStatus.PENDING.value,
        extra={},
    )
    session.add(task)
    await session.flush()
    return task


async def update_task(
    session: AsyncSession,
    user: User,
    task_id: UUID,
    *,
    title: str | None = None,
    due_at: datetime | None = None,
    task_type: str | None = None,
    priority: str | None = None,
) -> Task | None:
    task = await session.get(Task, task_id)
    if not task or task.user_id != user.id:
        return None
    if title is not None:
        task.title = title
    if due_at is not None:
        task.due_at = due_at
    if task_type is not None:
        task.task_type = task_type
    if priority is not None:
        task.priority = priority
    nt, pr, rem, pts, pen = merge_inference(
        title=task.title,
        task_type=task.task_type,
        due_at=task.due_at,
        priority=task.priority,
        reminder_at=task.reminder_at,
    )
    task.task_type = nt
    task.priority = pr
    task.reminder_at = rem
    task.points = pts
    task.penalty_text = pen
    await session.flush()
    return task


async def delete_task(session: AsyncSession, user: User, task_id: UUID) -> bool:
    task = await session.get(Task, task_id)
    if not task or task.user_id != user.id:
        return False
    await session.delete(task)
    return True


async def complete_task(session: AsyncSession, user: User, task_id: UUID) -> Task | None:
    task = await session.get(Task, task_id)
    if not task or task.user_id != user.id:
        return None
    if task.status != TaskStatus.PENDING.value:
        return task
    task.status = TaskStatus.COMPLETED.value
    task.completed_at = utc_now()
    user.total_score += task.points
    await session.flush()
    return task


async def pending_tasks_for_local_date(
    session: AsyncSession,
    user: User,
    local_d: date,
) -> list[Task]:
    start_utc, end_utc = local_day_bounds_utc(local_d, user.timezone)
    q = await session.execute(
        select(Task).where(
            and_(
                Task.user_id == user.id,
                Task.status == TaskStatus.PENDING.value,
                Task.due_at >= start_utc,
                Task.due_at < end_utc,
            )
        )
    )
    return list(q.scalars().all())


async def complete_all_pending_today(session: AsyncSession, user: User) -> list[Task]:
    from app.utils.timezone import local_date_at

    today = local_date_at(utc_now(), user.timezone)
    tasks = await pending_tasks_for_local_date(session, user, today)
    done: list[Task] = []
    for t in tasks:
        t.status = TaskStatus.COMPLETED.value
        t.completed_at = utc_now()
        user.total_score += t.points
        done.append(t)
    await session.flush()
    return done


async def complete_tasks_by_ids(
    session: AsyncSession,
    user: User,
    task_ids: list[UUID],
) -> list[Task]:
    done: list[Task] = []
    for tid in task_ids:
        t = await session.get(Task, tid)
        if not t or t.user_id != user.id:
            continue
        if t.status != TaskStatus.PENDING.value:
            continue
        t.status = TaskStatus.COMPLETED.value
        t.completed_at = utc_now()
        user.total_score += t.points
        done.append(t)
    await session.flush()
    return done


async def close_day(
    session: AsyncSession,
    user: User,
    local_d: date,
    *,
    notes: str | None = None,
) -> DayRecord:
    """Mark uncompleted tasks for local_d as missed; idempotent if already closed."""
    existing = await session.execute(
        select(DayRecord).where(
            DayRecord.user_id == user.id,
            DayRecord.local_date == local_d,
        )
    )
    rec = existing.scalar_one_or_none()
    if rec and rec.day_closed:
        return rec

    tasks = await pending_tasks_for_local_date(session, user, local_d)
    missed_count = 0
    score_delta = 0
    missed_ids: list[str] = []

    for t in tasks:
        t.status = TaskStatus.MISSED.value
        user.total_score = max(0, user.total_score - t.points)
        score_delta -= t.points
        missed_count += 1
        missed_ids.append(str(t.id))

    start_utc, end_utc = local_day_bounds_utc(local_d, user.timezone)
    comp_q = await session.execute(
        select(Task).where(
            and_(
                Task.user_id == user.id,
                Task.status == TaskStatus.COMPLETED.value,
                Task.due_at >= start_utc,
                Task.due_at < end_utc,
            )
        )
    )
    completed_tasks = list(comp_q.scalars().all())
    completed_count = len(completed_tasks)

    summary = {
        "missed_task_ids": missed_ids,
        "penalties_applied": [t.penalty_text for t in tasks],
    }

    if rec is None:
        rec = DayRecord(
            user_id=user.id,
            local_date=local_d,
            day_closed=True,
            closed_at=utc_now(),
            completed_count=completed_count,
            missed_count=missed_count,
            score_delta=score_delta,
            notes=notes,
            summary=summary,
        )
        session.add(rec)
    else:
        rec.day_closed = True
        rec.closed_at = utc_now()
        rec.completed_count = completed_count
        rec.missed_count = missed_count
        rec.score_delta = score_delta
        rec.notes = notes
        rec.summary = summary

    await session.flush()
    return rec
