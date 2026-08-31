"""Single entry point: aiogram polling + APScheduler + FastAPI (uvicorn)."""

import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

import uvicorn

from api.main import app
from bot.main import dp
from config import settings
from db import init_db
from scheduler import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("qk_notes.run")


async def run_bot() -> None:
    from aiogram import Bot

    from bot.commands import set_bot_commands

    bot = Bot(token=settings.bot_token)
    await set_bot_commands(bot)
    start_scheduler(bot)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


async def main() -> None:
    settings.validate()
    await init_db()

    port = int(os.getenv("PORT", "8000"))
    uvicorn_config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(uvicorn_config)

    await asyncio.gather(run_bot(), server.serve())


if __name__ == "__main__":
    asyncio.run(main())

