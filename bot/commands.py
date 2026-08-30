"""Bot commands: /start, /help, /actionbutton, /backtap."""

import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from locales.i18n import t

logger = logging.getLogger("qk_notes.commands")

router = Router()


def _webapp_keyboard(lang: str):
    # Telegram only accepts HTTPS URLs for WebApp buttons; skip locally.
    if not settings.webapp_url or not settings.webapp_url.startswith("https://"):
        return None
    builder = InlineKeyboardBuilder()
    builder.button(text=t(lang, "open_webapp"), web_app=WebAppInfo(url=settings.webapp_url))
    return builder.as_markup()


@router.message(CommandStart())
async def start_handler(message: Message, db_user: dict) -> None:
    lang = db_user.get("language", "en")
    await message.answer(t(lang, "start"), reply_markup=_webapp_keyboard(lang))


@router.message(Command("help"))
async def help_handler(message: Message, db_user: dict) -> None:
    lang = db_user.get("language", "en")
    await message.answer(t(lang, "help"))


@router.message(Command("actionbutton"))
async def actionbutton_handler(message: Message, db_user: dict) -> None:
    lang = db_user.get("language", "en")
    await message.answer(t(lang, "actionbutton_guide"), reply_markup=_webapp_keyboard(lang))


@router.message(Command("backtap"))
async def backtap_handler(message: Message, db_user: dict) -> None:
    lang = db_user.get("language", "en")
    await message.answer(t(lang, "backtap_guide"), reply_markup=_webapp_keyboard(lang))
