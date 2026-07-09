"""
translator_v2/maltese/lexicon/terminology.py

Structured terminology and preferred term overrides.
"""
from __future__ import annotations

import re

# Preferred terminology mappings for untranslated English terms in OPUS output.
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

# Invalid/non-preferred Maltese surfaces emitted by OPUS or old data.
# Values are dictionary/preferred base surfaces; final spelling fixes happen later.
PREFERRED_MALTESE_TERMS: dict[str, str] = {
    "bieraħ": "lbieraħ",
}


def _preserve_case(source: str, target: str) -> str:
    if source.isupper():
        return target.upper()
    if source and source[0].isupper():
        return target[0].upper() + target[1:]
    return target


def apply_terminology_overrides(text: str) -> str:
    """Apply English term overrides and Maltese preferred surface normalization."""
    if not text:
        return ""

    cleaned = text
    for eng, mlt in PREFERRED_TERMS.items():
        pattern = re.compile(rf"\b{re.escape(eng)}\b", re.IGNORECASE)
        cleaned = pattern.sub(lambda m: _preserve_case(m.group(0), mlt), cleaned)

    for surface, preferred in PREFERRED_MALTESE_TERMS.items():
        pattern = re.compile(rf"\b{re.escape(surface)}\b", re.IGNORECASE)
        cleaned = pattern.sub(lambda m, p=preferred: _preserve_case(m.group(0), p), cleaned)

    return cleaned