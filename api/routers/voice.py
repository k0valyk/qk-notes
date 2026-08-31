"""Mini App in-app voice recording endpoint (transcribe -> classify -> save)."""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from api.auth import get_current_user
from config import settings
from db import log_usage, upsert_user

logger = logging.getLogger("qk_notes.voice_api")

router = APIRouter(tags=["voice"])


@router.post("/api/voice")
async def record_voice(audio: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Receive a voice recording from the Mini App, transcribe it with Groq,
    auto-classify it and save it to the right table. Returns the result."""
    if not audio or not getattr(audio, "filename", None):
        raise HTTPException(status_code=400, detail="audio required")

    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty audio")

    from groq_client import groq_client

    try:
        transcription = await groq_client.audio.transcriptions.create(
            file=("voice.webm", data),
            model=settings.groq_transcription_model,
            response_format="json",
        )
    except Exception as exc:
        await log_usage("mini_app_transcription", user["id"], "error", str(exc))
        logger.exception("Mini App transcription failed")
        raise HTTPException(status_code=502, detail="transcription failed")

    text = (transcription.text or "").strip()
    if not text:
        await log_usage("mini_app_transcription", user["id"], "error", "empty")
        return {"saved": False, "error": "no_speech"}

    await log_usage("mini_app_transcription", user["id"], "ok")

    db_user = await upsert_user(
        user_id=user["id"],
        username=user.get("username"),
        first_name=user.get("first_name"),
    )
    lang = db_user.get("language", "en")

    from bot.voice import run_pipeline

    try:
        record_id, classification = await run_pipeline(text, user["id"], lang)
    except Exception as exc:
        await log_usage("mini_app_save", user["id"], "error", str(exc))
        raise HTTPException(status_code=502, detail="save failed")

    await log_usage("mini_app_save", user["id"], "ok", classification["type"])
    return {
        "saved": True,
        "record_type": classification["type"],
        "record_id": record_id,
        "text": text,
    }