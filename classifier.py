import json
import logging

from config import settings
from groq_client import groq_client

logger = logging.getLogger("qk_notes.classifier")

SYSTEM_PROMPT = """You are a note classification assistant for the QK NOTES voice planner bot.
Given a transcribed voice note, return ONLY a JSON object (no markdown, no preamble) with these fields:
{
  "type": "plan" | "note" | "meeting" | "reminder",
  "subsection": see rules below,
  "title": "short 3-6 word title summarizing the note",
  "datetime": "ISO 8601 datetime if the note mentions a specific date/time/event, otherwise null",
  "summary": "one sentence summary of the note"
}

Type rules:
- "plan" — a task / to-do / something the user needs to do. subsection must be "in_progress".
- "note" — a general note or a thought. subsection must be "note" or "idea".
- "meeting" — a meeting / appointment / call with someone. subsection must be "upcoming".
- "reminder" — "remind me about X at ..." — the user asks to be notified at a specific time. subsection must be "remind". A "reminder" MUST have a datetime.

Respond in the same language as the note."""


async def classify_note(text: str) -> dict:
    try:
        response = await groq_client.chat.completions.create(
            model=settings.classification_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        # Strip markdown code fences if the model wraps JSON in them.
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start:end + 1]
        data = json.loads(raw)
        note_type = data.get("type") if data.get("type") in ("plan", "note", "meeting", "reminder") else "note"
        return {
            "type": note_type,
            "subsection": data.get("subsection"),
            "title": data.get("title"),
            "datetime": data.get("datetime"),
            "summary": data.get("summary"),
        }
    except Exception:
        logger.exception("Classification failed")
        return {
            "type": "note",
            "subsection": "note",
            "title": None,
            "datetime": None,
            "summary": None,
        }