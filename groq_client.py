"""Shared Groq API client.

A single AsyncGroq instance is created once and reused across the whole
application (bot handlers, classifier, future API layer) instead of
instantiating a new client on every request.
"""

from groq import AsyncGroq

from config import settings

groq_client = AsyncGroq(api_key=settings.groq_api_key)
