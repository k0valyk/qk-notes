import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


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
    database_path: str = os.getenv("DATABASE_PATH", "data/qk_notes.db")

    # Production host for the Mini App. Telegram only shows WebApp buttons for
    # public HTTPS URLs, so we ignore any non-HTTPS / localhost value.
    _PROD_WEBAPP = "https://qk-notes-production.up.railway.app/webapp/"

    @property
    def webapp_url(self) -> str:
        raw = os.getenv("WEBAPP_URL", self._PROD_WEBAPP)
        if not raw or not raw.startswith("https://") or "localhost" in raw:
            return self._PROD_WEBAPP
        raw = raw.rstrip("/")
        if raw.endswith("/webapp"):
            return raw + "/"
        if "/webapp/" not in raw and not raw.endswith("/webapp/index.html"):
            return raw + "/webapp/"
        return raw.rstrip("/") + "/"

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
