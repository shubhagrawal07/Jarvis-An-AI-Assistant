from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import Task, User
from app.db.session import get_db
from app.schemas.tasks import TaskCreateIn, TaskOut, TaskUpdateIn
from app.services import task_service
from app.utils.timezone import local_day_bounds_utc, utc_now

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskOut])
async def list_tasks(
    today: bool = Query(False),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Task]:
    if today:
        from app.utils.timezone import local_date_at

        d = local_date_at(utc_now(), user.timezone)
        start_utc, end_utc = local_day_bounds_utc(d, user.timezone)
        q = await session.execute(
            select(Task)
            .where(
                and_(
                    Task.user_id == user.id,
                    Task.due_at >= start_utc,
                    Task.due_at < end_utc,
                )
            )
            .order_by(Task.due_at.asc())
        )
        return list(q.scalars().all())
    q = await session.execute(
        select(Task).where(Task.user_id == user.id).order_by(Task.due_at.desc()).limit(200)
    )
    return list(q.scalars().all())


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task_manual(
    body: TaskCreateIn,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Task:
    task = await task_service.create_task(
        session,
        user,
        title=body.title,
        task_type=body.task_type,
        due_at=body.due_at,
        priority=body.priority,
        reminder_at=body.reminder_at,
    )
    try:
        from app.workers.celery_app import schedule_task_reminder
        from app.workers.tasks import sync_calendar_task

        if task.reminder_at:
            schedule_task_reminder(str(task.id), task.reminder_at)
        sync_calendar_task.delay(str(task.id))
    except Exception:
        pass
    return task


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Task:
    t = await session.get(Task, task_id)
    if not t or t.user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    return t


@router.patch("/{task_id}", response_model=TaskOut)
async def patch_task(
    task_id: UUID,
    body: TaskUpdateIn,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Task:
    t = await task_service.update_task(
        session,
        user,
        task_id,
        title=body.title,
        due_at=body.due_at,
        task_type=body.task_type,
        priority=body.priority,
    )
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        from app.workers.tasks import sync_calendar_task

        sync_calendar_task.delay(str(t.id))
    except Exception:
        pass
    return t


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_task(
    task_id: UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    t = await session.get(Task, task_id)
    gid = t.google_event_id if t and t.user_id == user.id else None
    ok = await task_service.delete_task(session, user, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    if gid:
        try:
            from app.workers.tasks import delete_calendar_event_task

            delete_calendar_event_task.delay(gid, str(user.id))
        except Exception:
            pass


@router.post("/{task_id}/complete", response_model=TaskOut)
async def complete(
    task_id: UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Task:
    t = await task_service.complete_task(session, user, task_id)
    if not t:
        raise HTTPException(status_code=404, detail="Not found")
    return t
