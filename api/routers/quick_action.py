"""Quick action endpoints: token management and the webhook for iOS Shortcuts."""

import io
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from api.auth import get_current_user
from config import settings
from db import create_quick_action_token, get_token_user

logger = logging.getLogger("qk_notes.quick_action")

router = APIRouter(prefix="/api/quick-action", tags=["quick-action"])


@router.get("/token")
async def get_token(user: dict = Depends(get_current_user)):
    token = await create_quick_action_token(user["id"])
    base = settings.webapp_url.split("?")[0].replace("/webapp/", "").replace("/webapp", "")
    return {
        "token": token,
        "url": f"{base.rstrip('/')}/api/quick-action?token={token}",
    }


@router.post("")
@router.get("")
async def quick_action(request: Request, audio: UploadFile | None = File(None)):
    """Webhook for iOS Shortcuts: token -> user -> transcription/classification pipeline.
    Token may be passed as query param (?token=...) or form field; text as form field."""
    form = await request.form()
    token = request.query_params.get("token") or form.get("token")
    text = form.get("text")
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    user_id = await get_token_user(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    if audio is not None and getattr(audio, "filename", None):
        data = await audio.read()
        from groq_client import groq_client
        transcription = await groq_client.audio.transcriptions.create(
            file=("voice.m4a", data),
            model=settings.groq_transcription_model,
            response_format="json",
        )
        text = (transcription.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="No text or audio provided")

    from bot.voice import run_pipeline
    record_id, classification = await run_pipeline(text, user_id, "en")
    return {"ok": True, "record_id": record_id, "type": classification["type"]}
