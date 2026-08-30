from pathlib import Path
import datetime
import secrets

import aiosqlite
from config import settings


async def init_db() -> None:
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(settings.database_path) as db:
        # WAL mode allows concurrent reads/writes so the bot and the future
        # FastAPI backend can safely share one SQLite database.
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                telegram_file_id TEXT,
                section TEXT,
                subsection TEXT,
                title TEXT,
                note_datetime TEXT,
                short_description TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_notes_user_created
            ON notes(user_id, created_at)
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                photo_url TEXT,
                language TEXT NOT NULL DEFAULT 'en',
                theme TEXT NOT NULL DEFAULT 'dark',
                is_admin INTEGER NOT NULL DEFAULT 0,
                is_blocked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_active_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(user_id),
                title TEXT,
                text TEXT NOT NULL,
                subsection TEXT NOT NULL DEFAULT 'in_progress',
                datetime TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(user_id),
                title TEXT,
                text TEXT NOT NULL,
                subsection TEXT NOT NULL DEFAULT 'upcoming',
                datetime TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                archived_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(user_id),
                title TEXT,
                text TEXT NOT NULL,
                datetime TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                notified_at TEXT,
                archived_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                user_id INTEGER,
                timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                details TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quick_action_tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(user_id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


def _connect() -> aiosqlite.Connection:
    return aiosqlite.connect(settings.database_path)


def _row_to_dict(row) -> dict:
    return {k: row[k] for k in row.keys()} if row is not None else None


async def log_usage(event_type: str, user_id: int | None, status: str, details: str | None = None) -> None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "INSERT INTO usage_logs (event_type, user_id, status, details) VALUES (?, ?, ?, ?)",
            (event_type, user_id, status, details),
        )
        await db.commit()


# --- Record CRUD -----------------------------------------------------------


async def save_plan(user_id: int, text: str, subsection: str = "in_progress",
                    title: str | None = None, datetime_str: str | None = None) -> int:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "INSERT INTO plans (user_id, title, text, subsection, datetime) VALUES (?, ?, ?, ?, ?)",
            (user_id, title, text, subsection, datetime_str),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def save_meeting(user_id: int, text: str, subsection: str = "upcoming",
                       title: str | None = None, datetime_str: str | None = None) -> int:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "INSERT INTO meetings (user_id, title, text, subsection, datetime) VALUES (?, ?, ?, ?, ?)",
            (user_id, title, text, subsection, datetime_str),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def save_reminder(user_id: int, text: str, datetime_str: str,
                        title: str | None = None) -> int:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "INSERT INTO reminders (user_id, title, text, datetime) VALUES (?, ?, ?, ?)",
            (user_id, title, text, datetime_str),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def get_record(table: str, record_id: int, user_id: int | None = None) -> dict | None:
    assert table in ("plans", "meetings", "notes", "reminders")
    query = f"SELECT * FROM {table} WHERE id = ?"
    params: list = [record_id]
    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params)
        row = await cursor.fetchone()
        return _row_to_dict(row)


async def delete_record(table: str, record_id: int, user_id: int | None = None) -> bool:
    assert table in ("plans", "meetings", "notes", "reminders")
    query = f"DELETE FROM {table} WHERE id = ?"
    params: list = [record_id]
    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params)
        await db.commit()
        return cursor.rowcount > 0


async def update_record(table: str, record_id: int, user_id: int, fields: dict) -> None:
    assert table in ("plans", "meetings", "notes", "reminders")
    allowed = {
        "plans": {"title", "text", "subsection", "datetime"},
        "meetings": {"title", "text", "subsection", "datetime"},
        "notes": {"title", "text", "subsection", "short_description"},
        "reminders": {"title", "text", "datetime"},
    }[table]
    cols = [c for c in fields if c in allowed]
    if not cols:
        return
    sets = ", ".join(f"{c} = ?" for c in cols)
    params = [fields[c] for c in cols] + [record_id, user_id]
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        await db.execute(f"UPDATE {table} SET {sets} WHERE id = ? AND user_id = ?", params)
        await db.commit()


async def list_records(table: str, user_id: int, subsection: str | None = None) -> list[dict]:
    assert table in ("plans", "meetings", "notes", "reminders")
    query = "SELECT * FROM " + table + " WHERE user_id = ?"
    params: list = [user_id]
    if subsection:
        if table == "notes":
            query += " AND subsection = ?"
        else:
            query += " AND subsection = ?"
        params.append(subsection)
    if table == "reminders":
        query += " ORDER BY datetime"
    else:
        query += " ORDER BY created_at DESC"
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]


async def move_record(table: str, record_id: int, new_table: str, new_subsection: str | None) -> int | None:
    """Move a record between tables (the 'fix category' feature).
    Accepts either table names or type names (plan/note/meeting/reminder)."""
    table_map = {"plan": "plans", "note": "notes", "meeting": "meetings", "reminder": "reminders"}
    table = table_map.get(table, table)
    new_table = table_map.get(new_table, new_table)
    assert table in ("plans", "meetings", "notes", "reminders")
    assert new_table in ("plans", "meetings", "notes", "reminders")
    rec = await get_record(table, record_id)
    if not rec:
        return None
    if new_table == "plans":
        new_id = await save_plan(rec["user_id"], rec["text"], new_subsection or "in_progress",
                                 rec.get("title"), rec.get("datetime") or rec.get("note_datetime"))
    elif new_table == "meetings":
        new_id = await save_meeting(rec["user_id"], rec["text"], new_subsection or "upcoming",
                                    rec.get("title"), rec.get("datetime") or rec.get("note_datetime"))
    elif new_table == "reminders":
        dt = rec.get("datetime") or rec.get("note_datetime")
        if not dt:
            return None
        new_id = await save_reminder(rec["user_id"], rec["text"], dt, rec.get("title"))
    else:
        new_id = await save_note(
            user_id=rec["user_id"],
            text=rec["text"],
            section=None,
            subsection=new_subsection or "note",
            title=rec.get("title"),
            note_datetime=rec.get("datetime"),
            short_description=rec.get("short_description") or rec.get("summary"),
        )
    await delete_record(table, record_id, rec["user_id"])
    return new_id


# --- Users / settings ------------------------------------------------------


async def update_user_settings(user_id: int, language: str | None = None, theme: str | None = None) -> None:
    sets, params = [], []
    if language:
        sets.append("language = ?")
        params.append(language)
    if theme:
        sets.append("theme = ?")
        params.append(theme)
    if not sets:
        return
    params.append(user_id)
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        await db.execute(f"UPDATE users SET {', '.join(sets)} WHERE user_id = ?", params)
        await db.commit()


# --- Quick action tokens ---------------------------------------------------


async def create_quick_action_token(user_id: int) -> str:
    token = secrets.token_urlsafe(24)
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        await db.execute("DELETE FROM quick_action_tokens WHERE user_id = ?", (user_id,))
        await db.execute("INSERT INTO quick_action_tokens (token, user_id) VALUES (?, ?)", (token, user_id))
        await db.commit()
    return token


async def get_token_user(token: str) -> int | None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT user_id FROM quick_action_tokens WHERE token = ?", (token,))
        row = await cursor.fetchone()
        return int(row["user_id"]) if row else None


# --- Scheduler helpers -----------------------------------------------------


async def get_due_reminders(now_iso: str) -> list[dict]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM reminders WHERE notified_at IS NULL AND datetime <= ? AND archived_at IS NULL",
            (now_iso,),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]


async def mark_reminder_notified(reminder_id: int) -> None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE reminders SET notified_at = CURRENT_TIMESTAMP WHERE id = ?", (reminder_id,)
        )
        await db.commit()


async def get_all_active_users() -> list[dict]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE is_blocked = 0")
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]


async def cleanup_old_records() -> None:
    """Delete completed plans, past meetings and fired reminders older than 3 months."""
    cutoff = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=90)).isoformat()
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "DELETE FROM plans WHERE subsection = 'done' AND completed_at IS NOT NULL AND completed_at < ?",
            (cutoff,),
        )
        await db.execute(
            "DELETE FROM meetings WHERE subsection = 'past' AND archived_at IS NOT NULL AND archived_at < ?",
            (cutoff,),
        )
        await db.execute(
            "DELETE FROM reminders WHERE notified_at IS NOT NULL AND notified_at < ?",
            (cutoff,),
        )
        await db.commit()


async def mark_completed(table: str, record_id: int, user_id: int) -> None:
    """Mark a plan as done or archive a past meeting."""
    if table == "plans":
        await update_record(table, record_id, user_id, {"subsection": "done"})
        async with _connect() as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                "UPDATE plans SET completed_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                (record_id, user_id),
            )
            await db.commit()
    elif table == "meetings":
        await update_record(table, record_id, user_id, {"subsection": "past"})
        async with _connect() as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                "UPDATE meetings SET archived_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                (record_id, user_id),
            )
            await db.commit()


# --- Admin helpers ---------------------------------------------------------


async def admin_list_users() -> list[dict]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users ORDER BY last_active_at DESC")
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]


async def set_user_blocked(user_id: int, blocked: bool) -> None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        await db.execute("UPDATE users SET is_blocked = ? WHERE user_id = ?",
                         (int(blocked), user_id))
        await db.commit()


async def admin_stats() -> dict:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        stats: dict = {}
        cursor = await db.execute("SELECT COUNT(*) AS c FROM users")
        stats["total_users"] = (await cursor.fetchone())["c"]
        for days, key in ((1, "active_today"), (7, "active_7d"), (30, "active_30d")):
            cursor = await db.execute(
                "SELECT COUNT(*) AS c FROM users WHERE last_active_at >= datetime('now', ?)",
                (f"-{days} days",),
            )
            stats[key] = (await cursor.fetchone())["c"]
        for table in ("plans", "meetings", "notes", "reminders"):
            cursor = await db.execute(f"SELECT COUNT(*) AS c FROM {table}")
            stats[f"total_{table}"] = (await cursor.fetchone())["c"]
        cursor = await db.execute(
            "SELECT COUNT(*) AS c FROM usage_logs WHERE event_type = 'transcription' AND status = 'ok'"
        )
        stats["total_transcriptions"] = (await cursor.fetchone())["c"]
        cursor = await db.execute(
            "SELECT COUNT(*) AS c FROM usage_logs WHERE event_type = 'classification' AND status = 'ok'"
        )
        stats["total_classifications"] = (await cursor.fetchone())["c"]
        return stats


async def admin_recent_logs(limit: int = 50) -> list[dict]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM usage_logs ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]






async def upsert_user(
    user_id: int,
    username: str | None = None,
    first_name: str | None = None,
    photo_url: str | None = None,
    is_admin: bool = False,
) -> dict:
    """Create the user on first contact, refresh profile fields and
    last_active_at on every subsequent message. Returns the user row."""
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """
            INSERT INTO users (user_id, username, first_name, photo_url, is_admin, last_active_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                photo_url = COALESCE(excluded.photo_url, users.photo_url),
                last_active_at = CURRENT_TIMESTAMP
            """,
            (user_id, username, first_name, photo_url, int(is_admin)),
        )
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        await db.commit()
        return _row_to_dict(row)


async def save_note(
    user_id: int,
    text: str,
    telegram_file_id: str | None = None,
    section: str | None = None,
    subsection: str | None = None,
    title: str | None = None,
    note_datetime: str | None = None,
    short_description: str | None = None,
) -> int:
    async with aiosqlite.connect(settings.database_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO notes (
                user_id, text, telegram_file_id,
                section, subsection, title, note_datetime, short_description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, text, telegram_file_id, section, subsection, title, note_datetime, short_description),
        )
        await db.commit()
        return int(cursor.lastrowid)