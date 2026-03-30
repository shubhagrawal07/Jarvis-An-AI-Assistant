"""Rule-based inference for priority, reminders, points, and penalties."""

from datetime import UTC, datetime, timedelta

from app.db.models import Priority, TaskType


def normalize_task_type(raw: str | None) -> str:
    if not raw:
        return TaskType.TASK.value
    lower = raw.lower()
    if "meet" in lower:
        return TaskType.MEETING.value
    if "deadline" in lower or lower == "deadline":
        return TaskType.DEADLINE.value
    return TaskType.TASK.value


def infer_priority(
    task_type: str,
    due_at: datetime | None,
    title: str = "",
) -> str:
    """Meeting/deadline → HIGH; scheduled (has due time) → MEDIUM; else LOW."""
    t = task_type.lower()
    title_l = title.lower()
    if t == TaskType.MEETING.value or "meeting" in title_l:
        return Priority.HIGH.value
    if t == TaskType.DEADLINE.value or "deadline" in title_l:
        return Priority.HIGH.value
    if due_at is not None:
        return Priority.MEDIUM.value
    return Priority.LOW.value


def infer_reminder_at(due_at: datetime, task_type: str, priority: str) -> datetime:
    """Meeting → 30 min before; others → 90 min before (between 1–2h)."""
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=UTC)
    tt = task_type.lower()
    if tt == TaskType.MEETING.value or "meeting" in tt:
        delta = timedelta(minutes=30)
    else:
        delta = timedelta(minutes=90)
    return due_at - delta


def points_for_priority(priority: str) -> int:
    mapping = {
        Priority.HIGH.value: 20,
        Priority.MEDIUM.value: 10,
        Priority.LOW.value: 5,
    }
    return mapping.get(priority.lower(), 10)


def penalty_for_priority(priority: str) -> str:
    mapping = {
        Priority.HIGH.value: "Run 1km",
        Priority.MEDIUM.value: "20 pushups",
        Priority.LOW.value: "10 pushups",
    }
    return mapping.get(priority.lower(), "10 pushups")


def merge_inference(
    *,
    title: str,
    task_type: str | None,
    due_at: datetime | None,
    priority: str | None,
    reminder_at: datetime | None,
) -> tuple[str, str, datetime | None, int, str]:
    """Returns (normalized_type, priority, reminder_at, points, penalty)."""
    nt = normalize_task_type(task_type)
    pr = priority.lower() if priority else infer_priority(nt, due_at, title)
    if pr not in (Priority.HIGH.value, Priority.MEDIUM.value, Priority.LOW.value):
        pr = infer_priority(nt, due_at, title)
    rem = reminder_at
    if rem is None and due_at is not None:
        rem = infer_reminder_at(due_at, nt, pr)
    pts = points_for_priority(pr)
    pen = penalty_for_priority(pr)
    return nt, pr, rem, pts, pen
