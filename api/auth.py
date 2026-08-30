"""Telegram WebApp initData verification (HMAC-SHA256 per Telegram docs)."""

import hashlib
import hmac
import json
import urllib.parse

from fastapi import Header, HTTPException

from config import settings


def parse_init_data(init_data: str) -> dict:
    """Validate Telegram WebApp initData and return the parsed user data."""
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid initData")

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="Missing initData hash")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", settings.bot_token.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, received_hash):
        raise HTTPException(status_code=401, detail="initData validation failed")

    if "user" in parsed:
        return json.loads(parsed["user"])
    raise HTTPException(status_code=401, detail="No user in initData")


async def get_current_user(x_telegram_init_data: str = Header(default="")) -> dict:
    """FastAPI dependency: authenticated Telegram user (id, username, ...)."""
    if not x_telegram_init_data:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-Init-Data header")
    return parse_init_data(x_telegram_init_data)
