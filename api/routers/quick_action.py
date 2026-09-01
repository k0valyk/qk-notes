"""Quick action endpoints: token management and the webhook for iOS Shortcuts."""

import datetime
import io
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from api.auth import get_current_user
from config import settings
from db import create_quick_action_token, get_token_user, log_usage, upsert_user

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
    """Webhook for iOS Shortcuts (Action Button / Back Tap): token -> user ->
    transcription/classification pipeline. Token may be passed as query param
    (?token=...) or form field; audio as multipart file, text as form field."""
    form = await request.form()
    token = request.query_params.get("token") or form.get("token")
    text = form.get("text")
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    user_id = await get_token_user(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    db_user = await upsert_user(user_id=user_id)
    lang = db_user.get("language", "en")

    if audio is not None:
        data = await audio.read()
        if data:
            from groq_client import groq_client
            filename = getattr(audio, "filename", None) or "voice.m4a"
            transcription = await groq_client.audio.transcriptions.create(
                file=(filename, data),
                model=settings.groq_transcription_model,
                response_format="json",
            )
            text = (transcription.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="No text or audio provided")

    from bot.voice import run_pipeline, TYPE_KEY
    record_id, classification = await run_pipeline(text, user_id, lang)
    await log_usage("quick_action", user_id, "ok", classification["type"])

    # Send a confirmation message to the user's chat so they see the result.
    from zoneinfo import ZoneInfo
    try:
        tz = ZoneInfo(settings.default_timezone)
    except Exception:
        tz = datetime.timezone.utc
    stamp = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    title_line = f"📌 {classification['title']}\n" if classification.get("title") else ""
    from locales.i18n import t
    message = (
        t(lang, "saved", record_type=t(lang, TYPE_KEY[classification["type"]]), record_id=record_id)
        + f"\n\n{title_line}📝 {text}\n" + t(lang, "added_at", time=stamp)
    )

    from aiogram import Bot
    bot = Bot(token=settings.bot_token)
    try:
        await bot.send_message(user_id, message)
    except Exception as exc:
        logger.warning("Could not send quick-action confirmation to %s: %s", user_id, exc)
    finally:
        await bot.session.close()

    return {"ok": True, "record_id": record_id, "type": classification["type"]}
