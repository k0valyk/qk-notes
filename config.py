import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _resolve_db_path() -> str:
    """Pick a database location that SURVIVES redeploys.

    Priority:
    1. DATABASE_PATH env (explicit override).
    2. Railway Volume mount path (RAILWAY_VOLUME_MOUNT_PATH is set automatically
       by Railway when a Volume is attached to the service) — data persists
       across deploys.
    3. Local ./data fallback for development.
    """
    env = os.getenv("DATABASE_PATH")
    if env:
        return env
    volume = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    if volume:
        return os.path.join(volume, "qk_notes.db")
    return "data/qk_notes.db"


@dataclass(frozen=True)
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    bot_username: str = os.getenv("BOT_USERNAME", "qk_notes_bot")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    admin_user_id: int = int(os.getenv("ADMIN_USER_ID", "6862120256"))
    groq_transcription_model: str = os.getenv(
        "GROQ_TRANSCRIPTION_MODEL",
        "whisper-large-v3-turbo",
    )
    classification_model: str = os.getenv(
        "CLASSIFICATION_MODEL",
        "openai/gpt-oss-120b",
    )
    default_timezone: str = os.getenv("DEFAULT_TIMEZONE", "Europe/Kyiv")
    database_path: str = _resolve_db_path()

    # Production host for the Mini App. Telegram only shows WebApp buttons for
    # public HTTPS URLs, so we ignore any non-HTTPS / localhost value.
    # Bump _WEBAPP_V to force Telegram WebView to load a fresh document.
    _WEBAPP_V = 10
    _PROD_BASE = "https://qk-notes-production.up.railway.app"

    @property
    def webapp_url(self) -> str:
        raw = os.getenv("WEBAPP_URL", f"{self._PROD_BASE}/webapp/")
        if not raw or not raw.startswith("https://") or "localhost" in raw:
            raw = f"{self._PROD_BASE}/webapp/"
        raw = raw.split("?")[0].rstrip("/")
        if not raw.endswith("/webapp"):
            raw = raw + "/webapp"
        return f"{raw}/?v={self._WEBAPP_V}"

    def validate(self) -> None:
        missing = []
        if not self.bot_token:
            missing.append("BOT_TOKEN")
        if not self.groq_api_key:
            missing.append("GROQ_API_KEY")

        if missing:
            raise RuntimeError(
                "Missing required environment variables: "
                + ", ".join(missing)
            )


settings = Settings()
