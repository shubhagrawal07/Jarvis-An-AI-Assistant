"""Intent orchestrator: OpenAI structured parsing + task dispatch."""

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Task, TaskStatus, User
from app.services import task_service
from app.utils.timezone import utc_now


class LlmIntent(BaseModel):
    action: str
    title: str | None = None
    due_iso: str | None = Field(None, alias="datetime")
    type: str | None = None
    priority: str | None = None
    reminder: str | None = None
    target: str | None = None
    updates: dict[str, Any] | None = None
    task_titles: list[str] | None = None
    scope: str | None = None  # e.g. all_today

    model_config = {"populate_by_name": True, "extra": "ignore"}


class OrchestratorResult(BaseModel):
    action: str
    message: str
    task_ids: list[str] = []
    detail: dict[str, Any] = {}


SYSTEM_PROMPT = """You are an intent parser for a personal task scheduler. Output a single JSON object only, no markdown.
Fields:
- action: one of create, update, delete, complete, bulk_complete, partial_complete
- For create: title, datetime (ISO 8601), type (meeting/task/deadline/other), priority (high/medium/low or null), reminder (ISO or null)
- For update: target (what user refers to), updates object with optional title, datetime (ISO), priority, type
- For delete: target
- For complete: target (single task description) OR scope=all_today for bulk
- For bulk_complete: scope=all_today
- For partial_complete: task_titles array of strings mentioned (e.g. ["meeting", "gym"])
Use null for unknown optional fields."""


def _client() -> OpenAI | None:
    key = get_settings().openai_api_key
    if not key:
        return None
    return OpenAI(api_key=key)


async def _candidate_tasks(session: AsyncSession, user: User, limit: int = 60) -> list[Task]:
    now = utc_now()
    q = await session.execute(
        select(Task)
        .where(
            and_(
                Task.user_id == user.id,
                Task.status == TaskStatus.PENDING.value,
                Task.due_at >= now - timedelta(days=1),
            )
        )
        .order_by(Task.due_at.asc())
        .limit(limit)
    )
    return list(q.scalars().all())


def _fallback_intent(text: str) -> dict[str, Any]:
    t = text.strip()
    low = t.lower()
    if "all" in low and "today" in low and any(
        x in low for x in ("complet", "done", "finished")
    ):
        return {"action": "bulk_complete", "scope": "all_today"}
    if low.startswith("schedule") or "remind me" in low:
        return {
            "action": "create",
            "title": t[:200],
            "datetime": (utc_now() + timedelta(hours=2)).isoformat(),
            "type": "task",
            "priority": None,
            "reminder": None,
        }
    return {
        "action": "create",
        "title": t or "New task",
        "datetime": (utc_now() + timedelta(hours=1)).isoformat(),
        "type": "task",
        "priority": None,
        "reminder": None,
    }


async def _llm_parse(text: str) -> dict[str, Any]:
    client = _client()
    if client is None:
        return _fallback_intent(text)
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        return data if isinstance(data, dict) else _fallback_intent(text)
    except Exception:
        return _fallback_intent(text)


async def _llm_repair(text: str, err: str) -> dict[str, Any]:
    client = _client()
    if client is None:
        return _fallback_intent(text)
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
                {"role": "user", "content": f"Validation error: {err}. Reply with fixed JSON only."},
            ],
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception:
        return _fallback_intent(text)


async def _resolve_task_ids(
    session: AsyncSession,
    user: User,
    utterance: str,
    candidates: list[Task],
) -> list[UUID]:
    if not candidates:
        return []
    client = _client()
    lines = [
        {"id": str(t.id), "title": t.title, "due_at": t.due_at.isoformat()}
        for t in candidates
    ]
    if client is None:
        # Keyword match fallback
        ids: list[UUID] = []
        u = utterance.lower()
        for t in candidates:
            if any(w for w in re.split(r"\W+", u) if len(w) > 2 and w in t.title.lower()):
                ids.append(t.id)
        return ids[:5]
    prompt = json.dumps({"utterance": utterance, "tasks": lines})
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Given the user utterance and tasks, return JSON {\"task_ids\": [uuid strings]}. "
                    "Pick tasks that best match. Empty array if none.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        out: list[UUID] = []
        for s in data.get("task_ids", []):
            try:
                out.append(UUID(str(s)))
            except ValueError:
                continue
        return out
    except Exception:
        return []


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return None


async def handle_command(session: AsyncSession, user: User, text: str) -> OrchestratorResult:
    raw = await _llm_parse(text)
    try:
        intent = LlmIntent.model_validate(raw)
    except ValidationError as e:
        raw2 = await _llm_repair(text, str(e))
        try:
            intent = LlmIntent.model_validate(raw2)
        except ValidationError:
            intent = LlmIntent.model_validate(_fallback_intent(text))

    action = intent.action.lower().strip()

    if action == "create":
        due = _parse_dt(intent.due_iso) or (utc_now() + timedelta(hours=1))
        task = await task_service.create_task(
            session,
            user,
            title=intent.title or "Task",
            task_type=intent.type,
            due_at=due,
            priority=intent.priority,
            reminder_at=_parse_dt(intent.reminder) if intent.reminder else None,
        )
        # Schedule Celery reminder
        try:
            from app.workers.celery_app import schedule_task_reminder
            from app.workers.tasks import sync_calendar_task

            if task.reminder_at:
                schedule_task_reminder(str(task.id), task.reminder_at)
            sync_calendar_task.delay(str(task.id))
        except Exception:
            pass
        return OrchestratorResult(
            action="create",
            message=f"Created task: {task.title}",
            task_ids=[str(task.id)],
            detail={"title": task.title},
        )

    candidates = await _candidate_tasks(session, user)

    if action in ("update", "delete", "complete"):
        target = intent.target or text
        ids = await _resolve_task_ids(session, user, target, candidates)
        if not ids and action == "complete" and intent.scope == "all_today":
            done = await task_service.complete_all_pending_today(session, user)
            return OrchestratorResult(
                action="bulk_complete",
                message=f"Marked {len(done)} task(s) complete.",
                task_ids=[str(t.id) for t in done],
            )
        if not ids:
            return OrchestratorResult(action=action, message="Could not match a task.", detail={})

        tid = ids[0]
        if action == "delete":
            t_del = await session.get(Task, tid)
            gid = t_del.google_event_id if t_del else None
            await task_service.delete_task(session, user, tid)
            try:
                from app.workers.tasks import delete_calendar_event_task

                if gid:
                    delete_calendar_event_task.delay(gid, str(user.id))
            except Exception:
                pass
            return OrchestratorResult(action="delete", message="Task deleted.", task_ids=[str(tid)])

        if action == "complete":
            t = await task_service.complete_task(session, user, tid)
            return OrchestratorResult(
                action="complete",
                message="Task completed.",
                task_ids=[str(tid)] if t else [],
            )

        if action == "update":
            upd = intent.updates or {}
            due = _parse_dt(upd.get("datetime")) if isinstance(upd.get("datetime"), str) else None
            t = await task_service.update_task(
                session,
                user,
                tid,
                title=upd.get("title") if isinstance(upd.get("title"), str) else None,
                due_at=due,
                task_type=upd.get("type") if isinstance(upd.get("type"), str) else None,
                priority=upd.get("priority") if isinstance(upd.get("priority"), str) else None,
            )
            if t:
                try:
                    from app.workers.tasks import sync_calendar_task

                    sync_calendar_task.delay(str(t.id))
                except Exception:
                    pass
            return OrchestratorResult(
                action="update",
                message="Task updated.",
                task_ids=[str(tid)],
            )

    if action == "bulk_complete" or intent.scope == "all_today":
        done = await task_service.complete_all_pending_today(session, user)
        return OrchestratorResult(
            action="bulk_complete",
            message=f"Marked {len(done)} task(s) complete.",
            task_ids=[str(t.id) for t in done],
        )

    if action == "partial_complete":
        titles = intent.task_titles or []
        matched: list[Task] = []
        for t in candidates:
            for phrase in titles:
                if phrase.lower() in t.title.lower() or phrase.lower() in t.task_type.lower():
                    matched.append(t)
                    break
        if not matched:
            ids = await _resolve_task_ids(session, user, text, candidates)
            matched = [t for t in candidates if t.id in ids]
        done = await task_service.complete_tasks_by_ids(session, user, [t.id for t in matched])
        return OrchestratorResult(
            action="partial_complete",
            message=f"Completed {len(done)} task(s).",
            task_ids=[str(t.id) for t in done],
        )

    return OrchestratorResult(action="unknown", message="Could not interpret command.", detail={})
