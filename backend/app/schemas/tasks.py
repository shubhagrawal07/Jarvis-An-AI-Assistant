from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TaskOut(BaseModel):
    id: UUID
    title: str
    task_type: str
    due_at: datetime
    priority: str
    reminder_at: datetime | None
    points: int
    penalty_text: str
    status: str
    completed_at: datetime | None
    google_event_id: str | None

    model_config = {"from_attributes": True}


class TaskCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    task_type: str | None = None
    due_at: datetime
    priority: str | None = None
    reminder_at: datetime | None = None


class TaskUpdateIn(BaseModel):
    title: str | None = None
    due_at: datetime | None = None
    task_type: str | None = None
    priority: str | None = None
