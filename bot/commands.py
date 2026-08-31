"""Bot commands: /start, /help, /actionbutton, /backtap + command menu + WebApp menu button."""

import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    BotCommandScopeDefault,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from locales.i18n import t

logger = logging.getLogger("qk_notes.commands")

router = Router()

COMMANDS_BY_LANG = {
    "en": [
        BotCommand(command="start", description="Open Mini App & main menu"),
        BotCommand(command="help", description="Help & commands"),
        BotCommand(command="actionbutton", description="Set up the Action Button"),
        BotCommand(command="backtap", description="Set up Back Tap"),
    ],
    "uk": [
        BotCommand(command="start", description="Відкрити Mini App і меню"),
        BotCommand(command="help", description="Допомога і команди"),
        BotCommand(command="actionbutton", description="Налаштувати Кнопку дії"),
        BotCommand(command="backtap", description="Налаштувати Тап по корпусу"),
    ],
    "ru": [
        BotCommand(command="start", description="Открыть Mini App и меню"),
        BotCommand(command="help", description="Помощь и команды"),
        BotCommand(command="actionbutton", description="Настроить Кнопку действия"),
        BotCommand(command="backtap", description="Настроить Тап по задней крышке"),
    ],
    "pl": [
        BotCommand(command="start", description="Otwórz Mini App i menu"),
        BotCommand(command="help", description="Pomoc i polecenia"),
        BotCommand(command="actionbutton", description="Skonfiguruj Przycisk akcji"),
        BotCommand(command="backtap", description="Skonfiguruj Stuknięcie w tył"),
    ],
    "es": [
        BotCommand(command="start", description="Abrir Mini App y menú"),
        BotCommand(command="help", description="Ayuda y comandos"),
        BotCommand(command="actionbutton", description="Configurar el Botón de acción"),
        BotCommand(command="backtap", description="Configurar el Toque trasero"),
    ],
}


async def set_bot_commands(bot) -> None:
    """Register the command menu (the "/" button) for every supported language."""
    try:
        for lang, cmds in COMMANDS_BY_LANG.items():
            await bot.set_my_commands(cmds, scope=BotCommandScopeDefault(), language_code=lang)
        await bot.set_my_commands(COMMANDS_BY_LANG["en"], scope=BotCommandScopeDefault())
    except Exception as exc:
        logger.warning("Failed to set bot commands: %s", exc)


def _webapp_keyboard(lang: str):
    # Telegram only accepts HTTPS URLs for WebApp buttons; skip locally.
    if not settings.webapp_url or not settings.webapp_url.startswith("https://"):
        return None
    builder = InlineKeyboardBuilder()
    builder.button(text=t(lang, "open_webapp"), web_app=WebAppInfo(url=settings.webapp_url))
    return builder.as_markup()


async def _ensure_menu_button(message: Message, lang: str) -> None:
    """A persistent WebApp menu button so the Mini App is always reachable
    from the chat (bottom-left of the keyboard, like popular bots)."""
    if not settings.webapp_url.startswith("https://"):
        return
    try:
        await message.bot.set_chat_menu_button(
            chat_id=message.chat.id,
            menu_button=MenuButtonWebApp(
                text=t(lang, "open_webapp"),
                web_app=WebAppInfo(url=settings.webapp_url),
            ),
        )
    except Exception as exc:
        logger.warning("Failed to set chat menu button: %s", exc)


@router.message(CommandStart())
async def start_handler(message: Message, db_user: dict) -> None:
    lang = db_user.get("language", "en")
    await _ensure_menu_button(message, lang)
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
