"""Shared CRUD factory for record routers (plans, notes, meetings, reminders)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import get_current_user
from db import get_record, delete_record, list_records, update_record


class RecordIn(BaseModel):
    title: str | None = None
    text: str = ""
    subsection: str | None = None
    datetime: str | None = None
    short_description: str | None = None


def make_records_router(table: str) -> APIRouter:
    router = APIRouter(prefix=f"/api/{table}", tags=[table])

    allowed_subsections = {
        "plans": ("in_progress", "done"),
        "notes": ("note", "idea"),
        "meetings": ("upcoming", "past"),
        "reminders": None,
    }[table]

    @router.get("")
    async def list_items(user: dict = Depends(get_current_user)):
        return await list_records(table, user["id"])

    @router.post("")
    async def create_item(body: RecordIn, user: dict = Depends(get_current_user)):
        subsection = body.subsection
        if table == "reminders":
            if not body.datetime:
                raise HTTPException(status_code=422, detail="datetime is required for reminders")
            from db import save_reminder
            record_id = await save_reminder(user["id"], body.text, body.datetime, body.title)
        elif table == "plans":
            from db import save_plan
            if subsection not in allowed_subsections:
                subsection = "in_progress"
            record_id = await save_plan(user["id"], body.text, subsection, body.title, body.datetime)
        elif table == "meetings":
            from db import save_meeting
            if subsection not in allowed_subsections:
                subsection = "upcoming"
            record_id = await save_meeting(user["id"], body.text, subsection, body.title, body.datetime)
        else:
            from db import save_note
            if subsection not in allowed_subsections:
                subsection = "note"
            record_id = await save_note(
                user_id=user["id"], text=body.text, section=None, subsection=subsection,
                title=body.title, note_datetime=body.datetime,
                short_description=body.short_description,
            )
        return {"id": record_id}

    @router.get("/{record_id}")
    async def get_item(record_id: int, user: dict = Depends(get_current_user)):
        rec = await get_record(table, record_id, user["id"])
        if not rec:
            raise HTTPException(status_code=404, detail="Not found")
        return rec

    @router.put("/{record_id}")
    async def update_item(record_id: int, body: RecordIn, user: dict = Depends(get_current_user)):
        fields = body.model_dump(exclude_none=False)
        if table == "reminders":
            fields.pop("subsection", None)
            fields.pop("short_description", None)
        await update_record(table, record_id, user["id"], fields)
        return {"ok": True}

    @router.delete("/{record_id}")
    async def delete_item(record_id: int, user: dict = Depends(get_current_user)):
        deleted = await delete_record(table, record_id, user["id"])
        if not deleted:
            raise HTTPException(status_code=404, detail="Not found")
        return {"ok": True}

    return router
