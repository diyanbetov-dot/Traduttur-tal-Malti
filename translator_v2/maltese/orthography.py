"""
translator_v2/maltese/orthography.py

Late-stage Maltese orthographic autocorrections.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from Essentials.dictionary_meanings import split_dictionary_line
from translator_v2.maltese.lexicon.database import get_lexicon_db

_VOWELS = set("aeiouàèìòùáéíóú")
_WORD_RE = re.compile(r"(?<!\w)([^\W\d_]+)(?!\w)", re.UNICODE)
_NOUN_FILES = ("fixednouns.dic", "places.dic", "eu_countries.dic", "dev_extra.dic")
_NOUN_TAGS = ("NOUN", "PROPN")
_LEXICAL_INITIAL_I_EXCEPTIONS = {"lbieraħ"}


def _finaldics_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "Essentials" / "finaldics"


@lru_cache(maxsize=1)
def _noun_surfaces() -> frozenset[str]:
    surfaces: set[str] = set()
    base_dir = _finaldics_dir()
    for name in _NOUN_FILES:
        path = base_dir / name
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.isdigit():
                continue
            surface, payload = split_dictionary_line(line)
            if not surface or not payload:
                continue
            tag = payload.split("-", 1)[0].upper()
            if any(noun_tag in tag for noun_tag in _NOUN_TAGS):
                surfaces.add(surface.lower())
    return frozenset(surfaces)


def _is_vowel_char(ch: str) -> bool:
    return ch.lower() == "għ" or ch.lower() in _VOWELS


def _letter_units(word: str) -> list[str]:
    letters = [ch for ch in word.lower() if ch.isalpha()]
    units: list[str] = []
    i = 0
    while i < len(letters):
        if letters[i] == "g" and i + 1 < len(letters) and letters[i + 1] == "ħ":
            units.append("għ")
            i += 2
        else:
            units.append(letters[i])
            i += 1
    return units


def _starts_with_consonant_cluster(word: str) -> bool:
    units = _letter_units(word)
    if len(units) < 2:
        return False
    return not _is_vowel_char(units[0]) and not _is_vowel_char(units[1])


def _needs_initial_i(text: str, start: int, word: str) -> bool:
    if not _starts_with_consonant_cluster(word):
        return False
    before = text[:start].rstrip()
    if not before:
        return True
    prev = before[-1]
    if prev in ".?!":
        return True
    return prev.isalpha() and not _is_vowel_char(prev)


def _is_dictionary_noun(word: str) -> bool:
    return word.lower() in _noun_surfaces()


def _is_dictionary_verb(word: str) -> bool:
    return bool(get_lexicon_db().lookup_verb(word.lower()))


def _starts_with_repeated_consonant(word: str) -> bool:
    units = _letter_units(word)
    return len(units) >= 2 and units[0] == units[1] and not _is_vowel_char(units[0])


def _verb_starts_with_j_consonant(word: str) -> bool:
    units = _letter_units(word)
    return len(units) >= 2 and units[0] == "j" and not _is_vowel_char(units[1])


def _prefix_initial_i(word: str) -> str:
    prefixed = "i" + word
    if word.isupper():
        return prefixed.upper()
    if word and word[0].isupper():
        return "I" + word[0].lower() + word[1:]
    return prefixed


def _replace_initial_j_with_i(word: str) -> str:
    if word.isupper():
        return "I" + word[1:]
    if word and word[0].isupper():
        return "I" + word[1:]
    return "i" + word[1:]


def apply_final_orthography(text: str) -> str:
    """Apply final, context-sensitive spelling fixes after translation is assembled."""
    if not text:
        return ""

    # 1. Convert x' to xi before words starting with a consonant cluster
    def replace_x(match: re.Match[str]) -> str:
        prefix = match.group(1)
        word = match.group(2)
        if _starts_with_consonant_cluster(word):
            return ("Xi" if prefix.isupper() else "xi") + " " + word
        return prefix + "'" + word

    text = re.sub(r"\b(x)['’ʼʻ´`‘]\s*([^\W\d_]+)", replace_x, text, flags=re.IGNORECASE)

    def replace(match: re.Match[str]) -> str:
        word = match.group(0)
        lower = word.lower()
        if lower.startswith("i"):
            return word
        if lower in _LEXICAL_INITIAL_I_EXCEPTIONS:
            return _prefix_initial_i(word) if _needs_initial_i(text, match.start(), word) else word
        if not _needs_initial_i(text, match.start(), word):
            return word
        if _is_dictionary_noun(word) and _starts_with_repeated_consonant(word):
            return _prefix_initial_i(word)
        if _is_dictionary_verb(word) and _starts_with_repeated_consonant(word):
            return _prefix_initial_i(word)
        if _is_dictionary_verb(word) and _verb_starts_with_j_consonant(word):
            return _replace_initial_j_with_i(word)
        return word

    return _WORD_RE.sub(replace, text)