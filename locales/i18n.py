"""Localization loader. All user-facing strings live in locales/<lang>.json."""

import json
from pathlib import Path

_LOCALES_DIR = Path(__file__).resolve().parent
SUPPORTED_LANGUAGES = ("en", "uk", "ru", "pl", "es")
DEFAULT_LANGUAGE = "en"

_cache: dict[str, dict] = {}


def _load(lang: str) -> dict:
    if lang not in _cache:
        path = _LOCALES_DIR / f"{lang}.json"
        if not path.exists():
            path = _LOCALES_DIR / f"{DEFAULT_LANGUAGE}.json"
        _cache[lang] = json.loads(path.read_text(encoding="utf-8"))
    return _cache[lang]


def t(lang: str, key: str, **kwargs) -> str:
    """Translate key for the given language with fallback to English."""
    data = _load(lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE)
    if key not in data:
        data = _load(DEFAULT_LANGUAGE)
    value = data.get(key, key)
    if kwargs:
        value = value.format(**kwargs)
    return value
