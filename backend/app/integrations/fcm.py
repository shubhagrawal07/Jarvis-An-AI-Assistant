"""Firebase Cloud Messaging — optional if credentials path is set."""

from __future__ import annotations

import threading

import firebase_admin
from firebase_admin import credentials, messaging

from app.config import get_settings

_lock = threading.Lock()
_app: firebase_admin.App | None = None


def _ensure_app() -> firebase_admin.App | None:
    global _app
    path = get_settings().firebase_credentials_path
    if not path:
        return None
    with _lock:
        if _app is None:
            try:
                _app = firebase_admin.get_app()
            except ValueError:
                cred = credentials.Certificate(path)
                _app = firebase_admin.initialize_app(cred)
        return _app


def send_push(fcm_token: str | None, title: str, body: str, data: dict | None = None) -> bool:
    if not fcm_token:
        return False
    app = _ensure_app()
    if app is None:
        return False
    try:
        msg = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            token=fcm_token,
        )
        messaging.send(msg)
        return True
    except Exception:
        return False
