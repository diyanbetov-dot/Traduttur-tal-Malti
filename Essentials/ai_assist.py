from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


TRUE_VALUES = {"1", "true", "yes", "on"}
VALID_PROVIDERS = {"gemini", "openai"}


@dataclass(frozen=True)
class AITranslationReview:
    enabled: bool
    used: bool
    data: dict[str, Any]
    error: str = ""


def ai_enabled() -> bool:
    return os.getenv("TRANSLATOR_AI_ENABLED", "").strip().casefold() in TRUE_VALUES


def ai_provider() -> str:
    explicit = os.getenv("TRANSLATOR_AI_PROVIDER", "").strip().casefold()
    if explicit:
        if explicit not in VALID_PROVIDERS:
            raise RuntimeError("TRANSLATOR_AI_PROVIDER must be 'gemini' or 'openai'.")
        return explicit
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    return "openai"


def ai_key_present() -> bool:
    provider = ai_provider()
    if provider == "gemini":
        return bool(os.getenv("GEMINI_API_KEY"))
    return bool(os.getenv("OPENAI_API_KEY"))


def ai_can_apply_repairs() -> bool:
    return os.getenv("TRANSLATOR_AI_APPLY_REPAIRS", "").strip().casefold() in TRUE_VALUES


def _json_from_ai_text(raw: str) -> dict[str, Any]:
    raw = (raw or "{}").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        raw = raw.removeprefix("json").strip()
    data = json.loads(raw)
    return data if isinstance(data, dict) else {"raw": raw}


_CLIENTS = {}


def _get_client(provider: str, api_key: str):
    key = (provider, api_key)
    if key in _CLIENTS:
        return _CLIENTS[key]
    if provider == "gemini":
        from google import genai
        client = genai.Client(api_key=api_key)
    elif provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    else:
        raise RuntimeError("Unsupported AI provider.")
    _CLIENTS[key] = client
    return client


def _generate_json(instructions: str, payload: dict[str, Any]) -> dict[str, Any]:
    provider = ai_provider()
    model = os.getenv(
        "GEMINI_MODEL" if provider == "gemini" else "OPENAI_MODEL",
        "gemini-2.5-flash" if provider == "gemini" else "gpt-4.1-mini",
    )

    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("TRANSLATOR_AI_ENABLED is set, but GEMINI_API_KEY is missing.")
        prompt = instructions + "\n\nInput JSON:\n" + json.dumps(payload, ensure_ascii=False)
        client = _get_client("gemini", api_key)
        response = client.models.generate_content(model=model, contents=prompt)
        return _json_from_ai_text(getattr(response, "text", "") or "{}")

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("TRANSLATOR_AI_ENABLED is set, but OPENAI_API_KEY is missing.")
    client = _get_client("openai", api_key)
    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=json.dumps(payload, ensure_ascii=False),
    )
    return _json_from_ai_text(getattr(response, "output_text", "") or "{}")


def review_translation(source: str, draft: str, direction: str) -> AITranslationReview:
    if not ai_enabled():
        return AITranslationReview(enabled=False, used=False, data={})
    instructions = (
        "You are a Maltese translation reviewer assisting a hybrid OPUS-MT translator. "
        "Do not replace the draft unless it is clearly wrong. Return compact JSON with: "
        "phrase_structure, sense_notes, gender_number_notes, ambiguity_notes, "
        "suggested_translation, should_override, confidence."
    )
    payload = {"direction": direction, "source": source, "draft_translation": draft}
    try:
        return AITranslationReview(enabled=True, used=True, data=_generate_json(instructions, payload))
    except Exception as exc:  # noqa: BLE001
        return AITranslationReview(enabled=True, used=False, data={}, error=str(exc))


def route_translation(source: str, direction: str) -> AITranslationReview:
    if not ai_enabled():
        return AITranslationReview(enabled=False, used=False, data={})
    instructions = (
        "Route this English input into the existing Maltese rule engine. Do not translate freely. "
        "Return compact JSON with route, subject, verb_gloss, object, tense, negated, explanation."
    )
    try:
        return AITranslationReview(enabled=True, used=True, data=_generate_json(instructions, {"direction": direction, "source": source}))
    except Exception as exc:  # noqa: BLE001
        return AITranslationReview(enabled=True, used=False, data={}, error=str(exc))


def review_to_note(review: AITranslationReview) -> str:
    if not review.enabled:
        return ""
    if review.error:
        return f"AI helper unavailable: {review.error}"
    if not review.used:
        return "AI helper enabled but did not run."
    parts: list[str] = []
    for key, label in (
        ("phrase_structure", "structure"),
        ("sense_notes", "sense"),
        ("gender_number_notes", "agreement"),
        ("ambiguity_notes", "ambiguity"),
    ):
        value = review.data.get(key)
        if value:
            parts.append(f"{label}: {value}")
    return "AI helper: " + " | ".join(str(part) for part in parts) if parts else "AI helper ran, but returned no review notes."


def translate_text(source: str, direction: str) -> str:
    if not ai_enabled():
        return ""
    try:
        data = _generate_json(
            "Translate this text. Return compact JSON with translated_text.",
            {"direction": direction, "source": source},
        )
        return str(data.get("translated_text", data.get("raw", ""))).strip()
    except Exception:
        return ""


def tag_sentence(source: str) -> list[dict[str, str]]:
    if not ai_enabled():
        return []
    try:
        data = _generate_json(
            "Analyze this English text. Return JSON containing tokens with word, lemma, pos, tense, person. Do not translate.",
            {"source": source},
        )
        tokens = data.get("tokens", [])
        return tokens if isinstance(tokens, list) else []
    except Exception:
        return []
