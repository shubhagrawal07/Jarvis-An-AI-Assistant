from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.command import CommandResultOut, CommandTextIn
from app.services.orchestrator import handle_command

router = APIRouter(prefix="/command", tags=["command"])


@router.post("/text", response_model=CommandResultOut)
async def command_text(
    body: CommandTextIn,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CommandResultOut:
    result = await handle_command(session, user, body.text)
    return CommandResultOut(
        action=result.action,
        message=result.message,
        task_ids=result.task_ids,
        detail=result.detail,
    )


@router.post("/voice", response_model=CommandResultOut)
async def command_voice(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    audio: UploadFile | None = File(None),
    text: str | None = Form(None),
) -> CommandResultOut:
    from openai import OpenAI

    from app.config import get_settings

    utterance = text or ""
    if audio is not None:
        raw = await audio.read()
        settings = get_settings()
        if not settings.openai_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OPENAI_API_KEY required for voice",
            )
        client = OpenAI(api_key=settings.openai_api_key)
        import io

        buf = io.BytesIO(raw)
        buf.name = audio.filename or "audio.m4a"
        tr = client.audio.transcriptions.create(model="whisper-1", file=buf)
        utterance = tr.text or ""
    if not utterance.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide text or a voice recording",
        )
    result = await handle_command(session, user, utterance)
    return CommandResultOut(
        action=result.action,
        message=result.message,
        task_ids=result.task_ids,
        detail=result.detail,
    )
