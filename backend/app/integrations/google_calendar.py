"""Google Calendar sync — requires OAuth refresh token on user."""

from datetime import UTC, timedelta
from uuid import UUID

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import get_settings
from app.core.crypto_tokens import decrypt_str
from app.db.models import Task, User
from app.db.sync_session import get_sync_session

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def _creds_for_user(user: User) -> Credentials | None:
    if not user.google_refresh_token:
        return None
    settings = get_settings()
    try:
        refresh = decrypt_str(user.google_refresh_token)
    except Exception:
        refresh = user.google_refresh_token
    return Credentials(
        None,
        refresh_token=refresh,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=SCOPES,
    )


def _calendar_service(creds: Credentials):
    if not creds.valid:
        creds.refresh(Request())
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def upsert_event_for_task(user_id: UUID, task_id: UUID) -> str | None:
    with get_sync_session() as session:
        user = session.get(User, user_id)
        task = session.get(Task, task_id)
        if not user or not task or task.user_id != user.id:
            return None
        creds = _creds_for_user(user)
        if not creds:
            return None
        try:
            service = _calendar_service(creds)
            body = {
                "summary": task.title,
                "start": {"dateTime": task.due_at.astimezone(UTC).isoformat()},
                "end": {
                    "dateTime": (
                        task.due_at.astimezone(UTC).replace(microsecond=0) + timedelta(hours=1)
                    ).isoformat()
                },
            }
            if task.google_event_id:
                service.events().patch(
                    calendarId="primary",
                    eventId=task.google_event_id,
                    body=body,
                ).execute()
                return task.google_event_id
            ev = service.events().insert(calendarId="primary", body=body).execute()
            eid = ev.get("id")
            if eid:
                task.google_event_id = eid
                session.flush()
            return eid
        except Exception:
            return None


def delete_event(user_id: UUID, google_event_id: str) -> bool:
    with get_sync_session() as session:
        user = session.get(User, user_id)
        if not user:
            return False
        creds = _creds_for_user(user)
        if not creds:
            return False
        try:
            service = _calendar_service(creds)
            service.events().delete(calendarId="primary", eventId=google_event_id).execute()
            return True
        except Exception:
            return False
