"""FastAPI application: REST API for the Mini App + static webapp serving."""

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.routers import admin, quick_action, records, settings
from db import init_db

logger = logging.getLogger("qk_notes.api")

app = FastAPI(title="QK NOTES API")

for table in ("plans", "notes", "meetings", "reminders"):
    app.include_router(records.make_records_router(table))
app.include_router(settings.router)
app.include_router(quick_action.router)
app.include_router(admin.router)


@app.on_event("startup")
async def startup() -> None:
    await init_db()
    logger.info("API started")


# Serve the Mini App frontend and locale files.
webapp_dir = ROOT / "webapp"
if webapp_dir.exists():
    app.mount("/webapp", StaticFiles(directory=str(webapp_dir), html=True), name="webapp")

locales_dir = ROOT / "locales"
if locales_dir.exists():
    app.mount("/locales", StaticFiles(directory=str(locales_dir)), name="locales")
