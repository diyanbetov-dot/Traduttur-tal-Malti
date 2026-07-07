from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AITranslationReview:
    enabled: bool
    used: bool
    data: dict[str, Any]
    error: str = ""


def ai_enabled() -> bool:
    # Hardcoded to False to turn the AI off
    return False


def _gemini_key() -> str:
    return os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY", "")


def ai_provider() -> str:
    explicit = os.getenv("TRANSLATOR_AI_PROVIDER", "").strip().casefold()
    if explicit in {"gemini", "openai"}:
        return explicit
    if _gemini_key():
        return "gemini"
    return "openai"


def ai_key_present() -> bool:
    if ai_provider() == "gemini":
        return bool(_gemini_key())
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
    _CLIENTS[key] = client
    return client


def _generate_json(instructions: str, payload: dict[str, Any]) -> dict[str, Any]:
    provider = ai_provider()
    model = os.getenv(
        "GEMINI_MODEL" if provider == "gemini" else "OPENAI_MODEL",
        "gemini-3.5-flash" if provider == "gemini" else "gpt-4.1-mini",
    )

    if provider == "gemini":
        gemini_key = _gemini_key()
        if not gemini_key:
            raise RuntimeError("TRANSLATOR_AI_ENABLED is set, but no Gemini key was found in GEMINI_API_KEY or OPENAI_API_KEY.")
        
        prompt = instructions + "\n\nInput JSON:\n" + json.dumps(payload, ensure_ascii=False)
        client = _get_client("gemini", gemini_key)
        response = client.models.generate_content(model=model, contents=prompt)
        return _json_from_ai_text(getattr(response, "text", "") or "{}")

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        raise RuntimeError("TRANSLATOR_AI_ENABLED is set, but OPENAI_API_KEY is missing.")

    client = _get_client("openai", openai_key)
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
        "You are a Maltese translation reviewer assisting a rule-based translator. "
        "Do not invent a full replacement unless the draft is clearly weak. "
        "Prefer preserving the draft and explaining phrase structure, sense choices, "
        "gender/number clues, tense, negation, and ambiguity. "
        "Return only compact JSON with these keys: "
        "phrase_structure, sense_notes, gender_number_notes, ambiguity_notes, "
        "suggested_translation, should_override, confidence."
    )
    payload = {
        "direction": direction,
        "source": source,
        "draft_translation": draft,
    }

    try:
        return AITranslationReview(enabled=True, used=True, data=_generate_json(instructions, payload))
    except Exception as exc:
        return AITranslationReview(enabled=True, used=False, data={}, error=str(exc))


def route_translation(source: str, direction: str) -> AITranslationReview:
    if not ai_enabled():
        return AITranslationReview(enabled=False, used=False, data={})

    instructions = (
        "Route this English input into the existing Maltese rule engine. "
        "Do not translate freely. Return only compact JSON. "
        "Supported route values: transitive_verb_object, none. "
        "For transitive_verb_object return: route, subject, verb_gloss, object, "
        "tense, negated, explanation. Use plain English dictionary glosses like "
        "miss, love, see, know, want. Use pronouns i,you,he,she,it,we,they,me,him,her,us,them."
    )
    payload = {"direction": direction, "source": source}

    try:
        return AITranslationReview(enabled=True, used=True, data=_generate_json(instructions, payload))
    except Exception as exc:
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
    if not parts:
        return "AI helper ran, but returned no review notes."
    return "AI helper: " + " | ".join(str(part) for part in parts)


def translate_text(source: str, direction: str) -> str:
    if not ai_enabled():
        return ""
    instructions = (
        "Translate this English text to Maltese. "
        "Return a compact JSON object with a single key: 'translated_text'."
    )
    payload = {
        "direction": direction,
        "source": source,
    }
    try:
        data = _generate_json(instructions, payload)
        return str(data.get("translated_text", data.get("raw", ""))).strip()
    except Exception:
        return ""


def tag_sentence(source: str) -> list[dict[str, str]]:
    if not ai_enabled():
        return []
    instructions = (
        "Analyze this English text and perform Part-of-Speech tagging and morphological analysis. "
        "Return a JSON object containing a list of `tokens`. "
        "Each token should have these keys: "
        "`word` (the original word), "
        "`lemma` (the base dictionary form, e.g. went -> go), "
        "`pos` (noun, verb, adjective, adverb, pronoun, preposition, conjunction, determiner), "
        "`tense` (for verbs: past, present, future; else empty), "
        "`person` (for verbs/pronouns: 1S, 2S, 3SM, 3SF, 1P, 2P, 3P; else empty). "
        "Do NOT translate the text."
    )
    payload = {"source": source}
    try:
        data = _generate_json(instructions, payload)
        return data.get("tokens", [])
    except Exception:
        return []
