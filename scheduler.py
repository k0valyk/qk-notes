"""APScheduler background jobs: daily digest, reminder notifications, cleanup."""

import asyncio
import datetime
import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from db import (
    cleanup_old_records,
    get_all_active_users,
    get_due_reminders,
    list_records,
    mark_reminder_notified,
    update_record,
)
from locales.i18n import t
from aiogram import Bot

from config import settings

logger = logging.getLogger("qk_notes.scheduler")

bot_ref: Bot | None = None


def _today_range() -> tuple[str, str]:
    now = datetime.datetime.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    end = now.replace(hour=23, minute=59, second=59).isoformat()
    return start, end


def _records_today(records: list[dict]) -> list[dict]:
    start, end = _today_range()
    return [r for r in records if r.get("datetime") and start <= r["datetime"] <= end]


async def _send_digest_for_user(bot: Bot, user: dict) -> None:
    lang = user.get("language", "en")
    user_id = user["user_id"]
    plans = _records_today(await list_records("plans", user_id))
    meetings = _records_today(await list_records("meetings", user_id))
    now = datetime.datetime.now()
    week_ahead = (now + datetime.timedelta(days=7)).isoformat()
    reminders = [
        r for r in await list_records("reminders", user_id)
        if r["datetime"] <= week_ahead and r["datetime"] >= now.isoformat(timespec="seconds")
    ]

    lines = [t(lang, "digest_header")]
    for title, items in (
        (t(lang, "digest_plans"), plans),
        (t(lang, "digest_meetings"), meetings),
        (t(lang, "digest_reminders"), reminders),
    ):
        lines.append(title)
        if not items:
            lines.append(t(lang, "digest_no_items"))
        else:
            for item in items:
                dt = f" ({item['datetime']})" if item.get("datetime") else ""
                name = item.get("title") or (item.get("text") or "")[:50]
                lines.append(f"  • {name}{dt}")
    lines.append("")
    lines.append(t(lang, "digest_hint"))
    await bot.send_message(user_id, "\n".join(lines))


async def digest_job() -> None:
    """Daily 8:00 digest for every active user."""
    if bot_ref is None:
        return
    for user in await get_all_active_users():
        try:
            await _send_digest_for_user(bot_ref, user)
        except Exception:
            logger.exception("Digest failed for user %s", user.get("user_id"))


async def reminders_job() -> None:
    """Notify about reminders whose time has come (runs every minute)."""
    if bot_ref is None:
        return
    now_iso = datetime.datetime.now().isoformat(timespec="seconds")
    for reminder in await get_due_reminders(now_iso):
        user_id = reminder["user_id"]
        try:
            user = next((u for u in await get_all_active_users() if u["user_id"] == user_id), None)
            lang = user.get("language", "en") if user else "en"
            await bot_ref.send_message(
                user_id,
                t(lang, "reminder_fired", title=reminder.get("title") or "—",
                  text=reminder["text"], datetime=reminder["datetime"]),
            )
            await mark_reminder_notified(reminder["id"])
        except Exception:
            logger.exception("Reminder notification failed for %s", user_id)


async def cleanup_job() -> None:
    """Daily cleanup of records older than 3 months."""
    await cleanup_old_records()
    logger.info("Cleanup job finished")


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    global bot_ref
    bot_ref = bot
    # pytz (used by APScheduler 3.x) still knows "Europe/Kiev", not "Europe/Kyiv".
    tz_name = settings.default_timezone
    try:
        import pytz
        tz = pytz.timezone(tz_name)
    except Exception:
        tz = tz_name
    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(digest_job, CronTrigger(hour=8, minute=0))
    scheduler.add_job(reminders_job, IntervalTrigger(minutes=1))
    scheduler.add_job(cleanup_job, CronTrigger(hour=3, minute=30))
    scheduler.start()
    logger.info("Scheduler started (digest 08:00 %s, reminders every minute, cleanup 03:30)",
                settings.default_timezone)
    return scheduler
