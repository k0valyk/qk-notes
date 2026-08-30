"""Admin API: users, stats, broadcast, logs. Only ADMIN_USER_ID is allowed."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user
from config import settings
from db import admin_list_users, admin_recent_logs, admin_stats, list_records, set_user_blocked

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("id") != settings.admin_user_id:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


@router.get("/users")
async def users(admin: dict = Depends(require_admin)):
    return await admin_list_users()


@router.get("/users/{user_id}")
async def user_detail(user_id: int, admin: dict = Depends(require_admin)):
    all_users = {u["user_id"]: u for u in await admin_list_users()}
    if user_id not in all_users:
        raise HTTPException(status_code=404, detail="User not found")
    records = {
        table: await list_records(table, user_id)
        for table in ("plans", "notes", "meetings", "reminders")
    }
    return {**all_users[user_id], "records": {k: len(v) for k, v in records.items()}}


@router.post("/users/{user_id}/block")
async def block_user(user_id: int, admin: dict = Depends(require_admin)):
    await set_user_blocked(user_id, True)
    return {"ok": True}


@router.post("/users/{user_id}/unblock")
async def unblock_user(user_id: int, admin: dict = Depends(require_admin)):
    await set_user_blocked(user_id, False)
    return {"ok": True}


@router.get("/stats")
async def stats(admin: dict = Depends(require_admin)):
    return await admin_stats()


@router.get("/logs")
async def logs(admin: dict = Depends(require_admin), limit: int = 50):
    return await admin_recent_logs(limit)


class BroadcastIn(BaseModel):
    message: str


@router.post("/broadcast")
async def broadcast(body: BroadcastIn, admin: dict = Depends(require_admin)):
    from scheduler import bot_ref
    sent, failed = 0, 0
    users = await admin_list_users()
    if bot_ref is not None:
        for u in users:
            try:
                await bot_ref.send_message(u["user_id"], body.message)
                sent += 1
            except Exception:
                failed += 1
    return {"ok": True, "sent": sent, "failed": failed, "total": len(users)}
