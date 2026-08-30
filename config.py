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
    webapp_url: str = os.getenv(
        "WEBAPP_URL", "https://qk-notes-production.up.railway.app"
    )
    default_timezone: str = os.getenv("DEFAULT_TIMEZONE", "Europe/Kyiv")
    database_path: str = os.getenv("DATABASE_PATH", "data/qk_notes.db")

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
