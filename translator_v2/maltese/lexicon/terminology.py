"""
translator_v2/maltese/lexicon/terminology.py

Structured terminology and preferred term overrides.
Enforces deterministic term replacements and handles common expressions
(e.g., downstairs -> isfel, upstairs -> fuq).
"""
from __future__ import annotations

import re

# Preferred terminology mappings (case-insensitive keys)
PREFERRED_TERMS: dict[str, str] = {
    "downstairs": "isfel",
    "upstairs": "fuq",
    "meadow": "marġ",
    "grass": "ħaxix",
    "little": "żgħir",
    "small": "żgħir",
    "large": "kbir",
    "green": "aħdar",
    "fresh": "frisk",
    "home": "dar",
    "work": "xogħol",
    "job": "xogħol",
    "anything": "xejn",
}


def apply_terminology_overrides(text: str) -> str:
    """
    Apply terminology overrides to translated text.
    Replaces untranslated English words with their preferred Maltese terms.
    """
    if not text:
        return ""

    cleaned = text
    for eng, mlt in PREFERRED_TERMS.items():
        # Match english word surrounded by word boundaries, case-insensitive
        pattern = re.compile(rf"\b{re.escape(eng)}\b", re.IGNORECASE)
        # Preserve capitalization of original if possible (simple heuristic)
        def replace(match: re.Match) -> str:
            val = match.group(0)
            if val.isupper():
                return mlt.upper()
            if val[0].isupper():
                return mlt[0].upper() + mlt[1:]
            return mlt
        cleaned = pattern.sub(replace, cleaned)

    return cleaned
