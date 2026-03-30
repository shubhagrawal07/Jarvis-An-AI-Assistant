from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DayCloseIn(BaseModel):
    local_date: date
    notes: str | None = None


class DayRecordOut(BaseModel):
    id: UUID
    local_date: date
    day_closed: bool
    closed_at: datetime | None
    completed_count: int
    missed_count: int
    score_delta: int
    notes: str | None
    summary: dict

    model_config = {"from_attributes": True}
