import enum
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Priority(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    MISSED = "missed"


class TaskType(str, enum.Enum):
    MEETING = "meeting"
    TASK = "task"
    DEADLINE = "deadline"
    OTHER = "other"


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    fcm_token: Mapped[str | None] = mapped_column(Text, nullable=True)

    google_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)

    morning_summary_hour: Mapped[int] = mapped_column(Integer, default=8)
    morning_summary_minute: Mapped[int] = mapped_column(Integer, default=0)
    eod_prompt_start_hour: Mapped[int] = mapped_column(Integer, default=21)
    eod_prompt_end_hour: Mapped[int] = mapped_column(Integer, default=23)

    total_score: Mapped[int] = mapped_column(Integer, default=0)

    tasks: Mapped[list["Task"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    day_records: Mapped[list["DayRecord"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    title: Mapped[str] = mapped_column(String(512))
    task_type: Mapped[str] = mapped_column(String(32), default=TaskType.TASK.value)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    priority: Mapped[str] = mapped_column(String(16), default=Priority.MEDIUM.value)
    reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    points: Mapped[int] = mapped_column(Integer, default=10)
    penalty_text: Mapped[str] = mapped_column(String(256), default="10 pushups")

    status: Mapped[str] = mapped_column(String(16), default=TaskStatus.PENDING.value, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    google_event_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    user: Mapped["User"] = relationship(back_populates="tasks")


class DayRecord(Base):
    __tablename__ = "day_records"
    __table_args__ = (UniqueConstraint("user_id", "local_date", name="uq_day_user_date"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    local_date: Mapped[date] = mapped_column(Date, index=True)

    day_closed: Mapped[bool] = mapped_column(default=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    completed_count: Mapped[int] = mapped_column(Integer, default=0)
    missed_count: Mapped[int] = mapped_column(Integer, default=0)
    score_delta: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    user: Mapped["User"] = relationship(back_populates="day_records")
