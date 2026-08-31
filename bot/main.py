import asyncio
import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.types import CallbackQuery, Message

from bot import commands, voice
from bot.commands import set_bot_commands
from config import settings
from db import init_db, upsert_user

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("qk_notes")

dp = Dispatcher()


class UserMiddleware(BaseMiddleware):
    """Auto-register the user on first contact, refresh last_active_at,
    and block messages from users with is_blocked = 1."""

    async def __call__(self, handler, event, data):
        tg_user = event.from_user
        if tg_user is not None:
            db_user = await upsert_user(
                user_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                is_admin=(tg_user.id == settings.admin_user_id),
            )
            if db_user.get("is_blocked"):
                blocked_msg = "⛔ Your access to QK NOTES has been restricted."
                if isinstance(event, (Message, CallbackQuery)):
                    if isinstance(event, CallbackQuery):
                        await event.answer(blocked_msg, show_alert=True)
                    else:
                        await event.answer(blocked_msg)
                return
            data["db_user"] = db_user
        return await handler(event, data)


dp.message.outer_middleware(UserMiddleware())
dp.callback_query.outer_middleware(UserMiddleware())

dp.include_router(commands.router)
dp.include_router(voice.router)


async def main() -> None:
    settings.validate()

    await init_db()

    bot = Bot(token=settings.bot_token)

    await set_bot_commands(bot)
    logger.info("Starting @%s", settings.bot_username)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

