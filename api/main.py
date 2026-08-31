"""FastAPI application: REST API for the Mini App + static webapp serving."""

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.routers import admin, quick_action, records, settings, voice
from db import init_db

logger = logging.getLogger("qk_notes.api")

app = FastAPI(title="QK NOTES API")


class NoCacheStaticFiles(StaticFiles):
    """Static files that browsers (incl. Telegram WebView) never cache stale."""

    def file_response(self, *args, **kwargs):  # type: ignore[override]
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        return response

for table in ("plans", "notes", "meetings", "reminders"):
    app.include_router(records.make_records_router(table))
app.include_router(settings.router)
app.include_router(quick_action.router)
app.include_router(voice.router)
app.include_router(admin.router)


@app.on_event("startup")
async def startup() -> None:
    await init_db()
    logger.info("API started")


# Serve the Mini App frontend and locale files.
webapp_dir = ROOT / "webapp"
if webapp_dir.exists():
    app.mount("/webapp", NoCacheStaticFiles(directory=str(webapp_dir), html=True), name="webapp")

locales_dir = ROOT / "locales"
if locales_dir.exists():
    app.mount("/locales", NoCacheStaticFiles(directory=str(locales_dir)), name="locales")
