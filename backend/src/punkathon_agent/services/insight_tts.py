from __future__ import annotations

import os

from dotenv import dotenv_values
from openai import OpenAI

from punkathon_agent.punkagent.constants import ENV_PATH

_INSIGHT_TTS_MODEL = "gpt-4o-mini-tts"
_INSIGHT_TTS_VOICE = "coral"
_MAX_INSIGHT_TTS_CHARS = 4000
_INSIGHT_TTS_INSTRUCTIONS = (
    "Parla in italiano con voce femminile, simpatica, stimolante e leggermente sarcastica. "
    "Il tono deve restare brillante, sicuro, naturale e mai caricaturale. "
    "Scandisci bene numeri e concetti chiave."
)


def _resolve_openai_api_key() -> str | None:
    file_values = dotenv_values(ENV_PATH)
    file_key = file_values.get("OPENAI_API_KEY")
    env_key = os.getenv("OPENAI_API_KEY")
    return file_key or env_key


def _normalize_insight_text(text: str) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        raise ValueError("Il testo dell'insight non puo' essere vuoto.")
    if len(normalized) > _MAX_INSIGHT_TTS_CHARS:
        raise ValueError("Il testo dell'insight e' troppo lungo per la sintesi vocale.")
    return normalized


def synthesize_insight_audio(text: str) -> bytes:
    api_key = _resolve_openai_api_key()
    if not api_key:
        raise ValueError("OPENAI_API_KEY non configurata.")

    client = OpenAI(api_key=api_key)
    normalized_text = _normalize_insight_text(text)

    with client.audio.speech.with_streaming_response.create(
        model=_INSIGHT_TTS_MODEL,
        voice=_INSIGHT_TTS_VOICE,
        input=normalized_text,
        instructions=_INSIGHT_TTS_INSTRUCTIONS,
        response_format="mp3",
    ) as response:
        return response.read()