"""Settings router: language, theme, account info."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.auth import get_current_user
from db import get_record, update_user_settings
from db import upsert_user
from config import settings


class SettingsIn(BaseModel):
    language: str | None = None
    theme: str | None = None
    digest_time: str | None = None


router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings(user: dict = Depends(get_current_user)):
    db_user = await upsert_user(
        user_id=user["id"],
        username=user.get("username"),
        first_name=user.get("first_name"),
        photo_url=user.get("photo_url"),
        is_admin=(user["id"] == settings.admin_user_id),
    )
    return {
        "user_id": db_user["user_id"],
        "username": db_user["username"],
        "first_name": db_user["first_name"],
        "photo_url": db_user["photo_url"],
        "language": db_user["language"],
        "theme": db_user["theme"],
        "digest_time": db_user.get("digest_time", "08:00"),
        "is_admin": bool(db_user["is_admin"]),
    }


@router.put("")
async def put_settings(body: SettingsIn, user: dict = Depends(get_current_user)):
    await update_user_settings(user["id"], body.language, body.theme, body.digest_time)
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user
