from pydantic import BaseModel

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/users", tags=["users"])


class MeOut(BaseModel):
    id: str
    email: str
    timezone: str
    total_score: int
    morning_summary_hour: int
    eod_prompt_start_hour: int
    eod_prompt_end_hour: int

    model_config = {"from_attributes": True}


class FcmIn(BaseModel):
    token: str


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(get_current_user)) -> MeOut:
    return MeOut(
        id=str(user.id),
        email=user.email,
        timezone=user.timezone,
        total_score=user.total_score,
        morning_summary_hour=user.morning_summary_hour,
        eod_prompt_start_hour=user.eod_prompt_start_hour,
        eod_prompt_end_hour=user.eod_prompt_end_hour,
    )


@router.patch("/me/fcm")
async def register_fcm(
    body: FcmIn,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    user.fcm_token = body.token
    await session.flush()
    return {"ok": True}
