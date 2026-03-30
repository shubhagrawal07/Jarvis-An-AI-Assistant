"""Google OAuth for Calendar — connect account."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.core.crypto_tokens import encrypt_str
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/auth/google", tags=["google"])

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def _flow() -> Flow:
    settings = get_settings()
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.google_redirect_uri],
            }
        },
        scopes=SCOPES,
        redirect_uri=settings.google_redirect_uri,
    )


@router.get("/authorize-url")
async def google_authorize_url(user: User = Depends(get_current_user)):
    """Returns URL for in-app browser (mobile)."""
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth not configured",
        )
    flow = _flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=str(user.id),
    )
    return {"authorization_url": auth_url}


@router.get("/start")
async def google_oauth_start(user: User = Depends(get_current_user)):
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth not configured",
        )
    flow = _flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=str(user.id),
    )
    return RedirectResponse(auth_url)


@router.get("/callback")
async def google_oauth_callback(
    session: AsyncSession = Depends(get_db),
    code: str | None = Query(None),
    state: str | None = Query(None),
):
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    try:
        user_id = UUID(state)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid state")

    flow = _flow()
    flow.fetch_token(code=code)
    creds = flow.credentials
    refresh = creds.refresh_token
    if not refresh:
        raise HTTPException(
            status_code=400,
            detail="No refresh token — revoke app access in Google account and retry",
        )

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.google_refresh_token = encrypt_str(refresh)
    await session.flush()
    return RedirectResponse("jarvis://oauth/google?connected=1")
