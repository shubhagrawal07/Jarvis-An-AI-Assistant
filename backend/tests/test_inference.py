from datetime import UTC, datetime

from app.services.inference import (
    infer_priority,
    infer_reminder_at,
    merge_inference,
    penalty_for_priority,
    points_for_priority,
)


def test_meeting_high_priority():
    assert infer_priority("meeting", datetime.now(UTC), "standup") == "high"


def test_deadline_high():
    assert infer_priority("deadline", datetime.now(UTC), "report") == "high"


def test_scheduled_medium():
    assert infer_priority("task", datetime.now(UTC), "chore") == "medium"


def test_points_and_penalties():
    assert points_for_priority("high") == 20
    assert "1km" in penalty_for_priority("high")
    assert points_for_priority("low") == 5


def test_reminder_meeting_30m():
    due = datetime(2026, 3, 31, 20, 0, tzinfo=UTC)
    r = infer_reminder_at(due, "meeting", "high")
    assert r.hour == 19 and r.minute == 30


def test_merge_inference():
    due = datetime(2026, 3, 31, 12, 0, tzinfo=UTC)
    nt, pr, rem, pts, pen = merge_inference(
        title="Team sync",
        task_type="meeting",
        due_at=due,
        priority=None,
        reminder_at=None,
    )
    assert pr == "high"
    assert pts == 20
    assert rem is not None
