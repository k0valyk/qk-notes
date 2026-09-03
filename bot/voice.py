"""Voice message handling and the shared transcribe -> classify -> save pipeline."""

import datetime
import io
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from classifier import classify_note
from config import settings
from db import log_usage, save_meeting, save_note, save_plan, save_reminder
from groq_client import groq_client
from locales.i18n import t

logger = logging.getLogger("qk_notes.voice")

router = Router()

TYPE_KEY = {
    "plan": "type_plan",
    "note": "type_note",
    "meeting": "type_meeting",
    "reminder": "type_reminder",
}

SUBSECTION_BY_TYPE = {
    "plan": "in_progress",
    "note": "note",
    "meeting": "upcoming",
    "reminder": "remind",
}

# Whisper language codes for transcription (so Ukrainian isn't mistaken for Russian).
WHISPER_LANG = {"en": "en", "uk": "uk", "ru": "ru", "pl": "pl", "es": "es"}


def whisper_lang(lang: str):
    """Return an ISO-639-1 Whisper language code, or None to auto-detect."""
    return WHISPER_LANG.get(lang)


async def transcribe(bot: Bot, file_id: str, language: str | None = None) -> str:
    """Download a Telegram voice message and transcribe it via Groq Whisper."""
    telegram_file = await bot.get_file(file_id)
    audio = io.BytesIO()
    await bot.download_file(telegram_file.file_path, destination=audio)
    audio.seek(0)
    kwargs = {
        "file": ("voice.ogg", audio.read()),
        "model": settings.groq_transcription_model,
        "response_format": "json",
    }
    lang = whisper_lang(language)
    if lang:
        kwargs["language"] = lang
    # Ask Whisper to restore punctuation/capitalization so the saved note
    # reads cleanly instead of one long lowercase stream of words.
    kwargs["prompt"] = (
        "Transcribe the speech exactly. Add correct punctuation marks and "
        "capitalization. Keep the original language. Output only the final text."
    )
    transcription = await groq_client.audio.transcriptions.create(**kwargs)
    return (transcription.text or "").strip()


def fix_category_keyboard(record_type: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"📋 {t('en', TYPE_KEY[rt])}", callback_data=f"fixcat:{rt}")]
        for rt in ("plan", "note", "meeting", "reminder") if rt != record_type
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def run_pipeline(text: str, user_id: int, language: str, telegram_file_id: str | None = None,
                       digest_reply: bool = False) -> tuple[int, dict]:
    """Classify text, save into the proper table, log usage. Returns (record_id, classification).
    digest_reply=True forces the record into today's plans/meetings (voice reply to digest)."""
    try:
        classification = await classify_note(text)
        await log_usage("classification", user_id, "ok")
    except Exception as exc:
        await log_usage("classification", user_id, "error", str(exc))
        raise

    note_type = classification["type"]
    subsection = classification["subsection"]
    title = classification["title"]
    dt = classification["datetime"]

    if digest_reply:
        if note_type not in ("plan", "meeting"):
            note_type = "plan"
        if not dt:
            dt = datetime.date.today().isoformat()
        classification["type"] = note_type
        classification["datetime"] = dt

    try:
        if note_type == "plan":
            record_id = await save_plan(user_id, text, "in_progress", title, dt)
        elif note_type == "meeting":
            record_id = await save_meeting(user_id, text, "upcoming", title, dt)
        elif note_type == "reminder" and dt:
            record_id = await save_reminder(user_id, text, dt, title)
        else:
            record_id = await save_note(
                user_id=user_id,
                text=text,
                telegram_file_id=telegram_file_id,
                section=None,
                subsection=subsection if subsection in ("note", "idea") else "note",
                title=title,
                note_datetime=dt,
                short_description=classification["summary"],
            )
            note_type = "note"
        await log_usage("save_record", user_id, "ok", note_type)
    except Exception as exc:
        await log_usage("save_record", user_id, "error", str(exc))
        raise
    classification["type"] = note_type
    return record_id, classification


async def _confirm_saved(status: Message, text: str, record_id: int, classification: dict, lang: str) -> None:
    """Edit the \"processing…\" message into the saved confirmation with a timestamp."""
    from zoneinfo import ZoneInfo
    try:
        tz = ZoneInfo(settings.default_timezone)
    except Exception:
        tz = datetime.timezone.utc
    stamp = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    title_line = f"📌 {classification['title']}\n" if classification["title"] else ""
    try:
        await status.edit_text(
            t(lang, "saved", record_type=t(lang, TYPE_KEY[classification["type"]]), record_id=record_id)
            + f"\n\n{title_line}📝 {text}\n" + t(lang, "added_at", time=stamp),
            reply_markup=fix_category_keyboard(classification["type"]),
        )
    except TelegramAPIError:
        logger.exception("Telegram API error while confirming save")


@router.message(F.voice)
async def voice_handler(message: Message, bot: Bot, db_user: dict) -> None:
    lang = db_user.get("language", "en")
    status = await message.answer(t(lang, "processing"))

    try:
        try:
            text = await transcribe(bot, message.voice.file_id, lang)
            await log_usage("transcription", db_user["user_id"], "ok")
        except Exception as exc:
            await log_usage("transcription", db_user["user_id"], "error", str(exc))
            logger.exception("Groq transcription failed")
            await status.edit_text(t(lang, "transcribe_failed"))
            return

        if not text:
            await status.edit_text(t(lang, "no_speech"))
            return

        digest_reply = bool(
            message.reply_to_message
            and message.reply_to_message.text
            and t(lang, "digest_header") in message.reply_to_message.text
        )

        record_id, classification = await run_pipeline(
            text, db_user["user_id"], lang, message.voice.file_id, digest_reply=digest_reply
        )

        await _confirm_saved(status, text, record_id, classification, lang)

    except TelegramAPIError:
        logger.exception("Telegram API error while processing voice message")
    except Exception:
        logger.exception("Voice processing failed")
        try:
            await status.edit_text(t(lang, "process_failed"))
        except Exception:
            pass


@router.message(F.text)
async def text_handler(message: Message, db_user: dict) -> None:
    """Plain text messages are classified and saved automatically —
    the bot decides by itself whether it is a plan, note, meeting or reminder."""
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return
    lang = db_user.get("language", "en")
    status = await message.answer(t(lang, "processing"))
    try:
        record_id, classification = await run_pipeline(text, db_user["user_id"], lang)
        await _confirm_saved(status, text, record_id, classification, lang)
    except TelegramAPIError:
        logger.exception("Telegram API error while processing text message")
    except Exception:
        logger.exception("Text processing failed")
        try:
            await status.edit_text(t(lang, "process_failed"))
        except Exception:
            pass


@router.callback_query(F.data.startswith("fixcat:"))
async def fix_category_handler(callback: CallbackQuery, db_user: dict) -> None:
    lang = db_user.get("language", "en")
    _, new_type = callback.data.split(":", 1)
    parts = callback.message.text.split("#")
    old_record_id = None
    if len(parts) > 1:
        digits = "".join(ch for ch in parts[1] if ch.isdigit())
        old_record_id = int(digits) if digits else None
    if not old_record_id:
        await callback.answer(t(lang, "category_unchanged"), show_alert=True)
        return
    from db import get_record, move_record

    for table in ("plans", "notes", "meetings", "reminders"):
        rec = await get_record(table, old_record_id, db_user["user_id"])
        if rec:
            new_id = await move_record(table, old_record_id, new_type, SUBSECTION_BY_TYPE[new_type])
            if new_id:
                await callback.message.edit_reply_markup(
                    reply_markup=fix_category_keyboard(new_type)
                )
                await callback.answer(
                    t(lang, "category_changed", record_type=t(lang, TYPE_KEY[new_type]), record_id=new_id)
                )
                return
    await callback.answer(t(lang, "category_unchanged"), show_alert=True)

