from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import DayRecord, User
from app.db.session import get_db
from app.schemas.day import DayCloseIn, DayRecordOut
from app.services import task_service

router = APIRouter(prefix="/day", tags=["day"])


@router.post("/close", response_model=DayRecordOut)
async def close_day(
    body: DayCloseIn,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DayRecord:
    rec = await task_service.close_day(session, user, body.local_date, notes=body.notes)
    return rec


@router.get("/records", response_model=list[DayRecordOut])
async def list_day_records(
    limit: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DayRecord]:
    q = await session.execute(
        select(DayRecord)
        .where(DayRecord.user_id == user.id)
        .order_by(DayRecord.local_date.desc())
        .limit(limit)
    )
    return list(q.scalars().all())
