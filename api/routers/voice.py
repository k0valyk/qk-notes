"""Mini App in-app voice recording endpoint (transcribe -> classify -> save)."""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from api.auth import get_current_user
from config import settings
from db import log_usage, upsert_user

logger = logging.getLogger("qk_notes.voice_api")

router = APIRouter(tags=["voice"])


@router.post("/api/voice")
async def record_voice(
    audio: UploadFile = File(...),
    save: str = "1",
    user: dict = Depends(get_current_user),
):
    """Receive a voice recording from the Mini App, transcribe it with Groq and
    auto-classify it. With save=0 only the transcription is returned so the user
    can review/edit the text in the Mini App before saving."""
    if not audio:
        raise HTTPException(status_code=400, detail="audio required")

    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty audio")

    from groq_client import groq_client

    filename = getattr(audio, "filename", None) or "voice.webm"
    try:
        transcription = await groq_client.audio.transcriptions.create(
            file=(filename, data),
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

    # Transcribe-only mode: return the text + classification for editing in the app.
    if save == "0":
        from classifier import classify_note
        try:
            classification = await classify_note(text)
            await log_usage("mini_app_classify", user["id"], "ok")
        except Exception:
            classification = {"type": "note", "title": None, "datetime": None}
        return {
            "saved": False,
            "edit": True,
            "text": text,
            "type": classification.get("type", "note"),
            "title": classification.get("title"),
            "datetime": classification.get("datetime"),
        }

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