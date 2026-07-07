"""
translator_v2/maltese/lexicon/database.py

In-memory database for Maltese lexical entries and verb paradigms.
Loads and indexes the .dic dictionary files on startup.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import NamedTuple

from Essentials.dictionary_meanings import parse_verb_payload, split_dictionary_line

logger = logging.getLogger(__name__)


class VerbFeatures(NamedTuple):
    lemma: str
    tense: str
    person: str
    negative: bool


class LexiconDatabase:
    """In-memory dictionary indexing surface forms to their morphological features."""

    def __init__(self, finaldics_dir: Path | None = None) -> None:
        self._dir = finaldics_dir or Path(__file__).resolve().parents[3] / "Essentials" / "finaldics"
        self._verbs: dict[str, list[VerbFeatures]] = {}
        # Reverse index: (lemma_lower, tense, person, negative) -> surface
        self._reverse_verbs: dict[tuple[str, str, str, bool], str] = {}
        self._is_loaded = False

    def load(self) -> None:
        """Load and parse verb paradigm dictionary files."""
        if self._is_loaded:
            return

        semitic_path = self._dir / "verbmt_semitic.dic"
        nonsemitic_path = self._dir / "verbmt_nonsemitic.dic"
        dev_path = self._dir / "dev_extra.dic"

        for path in (semitic_path, nonsemitic_path, dev_path):
            if not path.exists():
                logger.warning("Lexicon file not found: %s", path)
                continue
            self._load_file(path)

        self._is_loaded = True

    def _load_file(self, path: Path) -> None:
        try:
            # Read UTF-8 with BOM (utf-8-sig)
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            for line in text.splitlines():
                line = line.strip()
                if not line or line.isdigit():
                    continue

                surface, payload = split_dictionary_line(line)
                if not surface or not payload:
                    continue

                parsed = parse_verb_payload(payload)
                if parsed:
                    surface_lower = surface.lower()
                    lemma_lower = str(parsed["gloss"]).lower()
                    tense = str(parsed["tense"]).upper()
                    person = str(parsed["person"]).upper()
                    negative = bool(parsed["negative"])

                    features = VerbFeatures(
                        lemma=str(parsed["gloss"]),
                        tense=tense,
                        person=person,
                        negative=negative,
                    )
                    if surface_lower not in self._verbs:
                        self._verbs[surface_lower] = []
                    self._verbs[surface_lower].append(features)

                    # Populate reverse index (keep first match or shorter form)
                    rev_key = (lemma_lower, tense, person, negative)
                    if rev_key not in self._reverse_verbs:
                        self._reverse_verbs[rev_key] = surface
                    else:
                        # Collision resolution:
                        # 1. If the lemma is "to give", prioritize the root 'għtj' (the verb 'ta')
                        if lemma_lower == "to give":
                            payload_parts = payload.split("-")
                            if len(payload_parts) > 1 and payload_parts[1] == "għtj":
                                self._reverse_verbs[rev_key] = surface
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to load lexicon file %s: %s", path, exc)

    def lookup_verb(self, surface: str) -> list[VerbFeatures]:
        """Return all matching morphological features for a Maltese verb form."""
        self.load()
        return self._verbs.get(surface.lower(), [])

    def find_verb_surface(self, lemma: str, tense: str, person: str, negative: bool = False) -> str | None:
        """Find the matching surface form of a verb by its features."""
        self.load()
        return self._reverse_verbs.get((lemma.lower(), tense.upper(), person.upper(), negative))


# Singleton instance accessor
_db_instance: LexiconDatabase | None = None


def get_lexicon_db(finaldics_dir: Path | None = None) -> LexiconDatabase:
    global _db_instance
    if _db_instance is None:
        _db_instance = LexiconDatabase(finaldics_dir)
        _db_instance.load()
    return _db_instance
