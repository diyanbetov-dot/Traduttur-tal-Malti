"""
translator_v2/maltese/lexicon/database.py

In-memory database for Maltese lexical entries and verb paradigms.
Loads and indexes the .dic dictionary files on startup.

A binary pickle cache (lexicon_db.pkl) is maintained alongside the .dic files.
Loading from the cache (~230 ms) is ~6× faster than parsing raw text (~1.5 s).
The cache is regenerated automatically whenever a source .dic file is newer.
"""
from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import NamedTuple

from Essentials.dictionary_meanings import parse_verb_payload, split_dictionary_line

logger = logging.getLogger(__name__)

_CACHE_FILENAME = "lexicon_db.pkl"
_CACHE_VERSION = 2  # bump this to invalidate all existing caches


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

    # ------------------------------------------------------------------
    # Public loading entry point
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load verb paradigm data, preferring the binary cache for speed."""
        if self._is_loaded:
            return

        semitic_path = self._dir / "verbmt_semitic.dic"
        nonsemitic_path = self._dir / "verbmt_nonsemitic.dic"
        dev_path = self._dir / "dev_extra.dic"
        source_paths = [p for p in (semitic_path, nonsemitic_path, dev_path) if p.exists()]

        cache_path = self._dir / _CACHE_FILENAME
        if self._try_load_cache(cache_path, source_paths):
            self._is_loaded = True
            return

        # Cache miss — parse from text files and persist a fresh cache
        for path in source_paths:
            self._load_file(path)

        self._save_cache(cache_path)
        self._is_loaded = True

    # ------------------------------------------------------------------
    # Binary cache helpers
    # ------------------------------------------------------------------

    def _cache_is_fresh(self, cache_path: Path, source_paths: list[Path]) -> bool:
        """Return True only if cache exists, has the right version, and is newer than every source."""
        if not cache_path.exists():
            return False
        cache_mtime = cache_path.stat().st_mtime
        if any(p.stat().st_mtime > cache_mtime for p in source_paths):
            return False
        return True

    def _try_load_cache(self, cache_path: Path, source_paths: list[Path]) -> bool:
        """Attempt to load from the binary cache. Return True on success."""
        if not self._cache_is_fresh(cache_path, source_paths):
            return False
        try:
            with open(cache_path, "rb") as fh:
                payload = pickle.load(fh)
            if not isinstance(payload, dict) or payload.get("version") != _CACHE_VERSION:
                return False
            # Stored as plain (lemma, tense, person, negative) tuples for speed
            raw_verbs: dict[str, list[tuple]] = payload["verbs"]
            self._verbs = {
                surface: [VerbFeatures(*t) for t in tuples]
                for surface, tuples in raw_verbs.items()
            }
            self._reverse_verbs = payload["reverse_verbs"]
            logger.debug("Loaded LexiconDatabase from cache: %s", cache_path)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load lexicon cache (%s), falling back to text parse.", exc)
            self._verbs = {}
            self._reverse_verbs = {}
            return False

    def _save_cache(self, cache_path: Path) -> None:
        """Persist current index to a binary pickle file for fast future loads."""
        try:
            payload = {
                "version": _CACHE_VERSION,
                # Store as plain tuples (not NamedTuples) — ~2× faster to unpickle
                "verbs": {
                    surface: [tuple(f) for f in features]
                    for surface, features in self._verbs.items()
                },
                "reverse_verbs": self._reverse_verbs,
            }
            with open(cache_path, "wb") as fh:
                pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)
            logger.debug("Saved LexiconDatabase cache: %s", cache_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not save lexicon cache: %s", exc)

    # ------------------------------------------------------------------
    # Raw .dic file parser (fallback / cache generation)
    # ------------------------------------------------------------------

    def _load_file(self, path: Path) -> None:
        try:
            # Read UTF-8 with BOM (utf-8-sig)
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            for line in text.splitlines():
                line = line.strip()
                if not line or line.isdigit():
                    continue
                if "/" not in line:
                    continue

                surface, payload = split_dictionary_line(line)
                if not surface or not payload:
                    continue

                parsed = parse_verb_payload(payload)
                if parsed:
                    surface_lower = surface.lower()
                    # Normalize curly apostrophes to straight quote
                    surface_lower = surface_lower.replace("ʼ", "'").replace("’", "'").replace("‘", "'").replace("ʻ", "'").replace("´", "'")
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

    # ------------------------------------------------------------------
    # Public query API
    # ------------------------------------------------------------------

    def lookup_verb(self, surface: str) -> list[VerbFeatures]:
        """Return all matching morphological features for a Maltese verb form, with fallback for pronominal suffixes."""
        self.load()
        surface_lower = surface.lower()
        surface_lower = surface_lower.replace("ʼ", "'").replace("’", "'").replace("‘", "'").replace("ʻ", "'").replace("´", "'")

        res = self._verbs.get(surface_lower)
        if res:
            return res

        import re  # noqa: PLC0415
        suffixes = ["hom", "ha", "kom", "na", "ni", "ek", "k", "hu", "h", "lu", "li", "u"]
        for suff in suffixes:
            if surface_lower.endswith(suff):
                base = surface_lower[:-len(suff)]
                res = self._verbs.get(base)
                if res:
                    return res
                # Check for vowel changes before final consonants (e.g. nifhim -> nifhem)
                match = re.match(r"^(.*)i([bdfgklmnrstxz])$", base)
                if match:
                    base_alt = match.group(1) + "e" + match.group(2)
                    res = self._verbs.get(base_alt)
                    if res:
                        return res
                res = self._verbs.get(base + "'")
                if res:
                    return res
        return []

    def find_verb_surface(self, lemma: str, tense: str, person: str, negative: bool = False) -> str | None:
        """Find the matching surface form of a verb by its features."""
        self.load()
        return self._reverse_verbs.get((lemma.lower(), tense.upper(), person.upper(), negative))


_NOUN_CACHE_FILENAME = "nouns_db.pkl"
_NOUN_CACHE_VERSION = 2


class NounDatabase:
    """In-memory database caching Maltese noun genders parsed from fixednouns.dic."""

    def __init__(self, finaldics_dir: Path | None = None) -> None:
        self._dir = finaldics_dir or Path(__file__).resolve().parents[3] / "Essentials" / "finaldics"
        self._nouns: dict[str, str] = {}  # mlt_noun -> gender (F/M)
        self._english_to_nouns: dict[str, list[tuple[str, str]]] = {}  # eng_lemma -> [(mlt_noun, gender)]
        self._is_loaded = False

    def load(self) -> None:
        if self._is_loaded:
            return

        dic_path = self._dir / "fixednouns.dic"
        if not dic_path.exists():
            return

        cache_path = self._dir / _NOUN_CACHE_FILENAME
        # Check cache freshness against the fixednouns.dic source file
        if self._try_load_cache(cache_path, [dic_path]):
            self._is_loaded = True
            return

        # Cache miss — parse from text and write binary cache
        self._load_file(dic_path)
        self._save_cache(cache_path)
        self._is_loaded = True

    def _try_load_cache(self, cache_path: Path, source_paths: list[Path]) -> bool:
        if not cache_path.exists():
            return False
        cache_mtime = cache_path.stat().st_mtime
        if any(p.stat().st_mtime > cache_mtime for p in source_paths):
            return False
        try:
            with open(cache_path, "rb") as fh:
                payload = pickle.load(fh)
            if not isinstance(payload, dict) or payload.get("version") != _NOUN_CACHE_VERSION:
                return False
            self._nouns = payload["nouns"]
            self._english_to_nouns = payload["english_to_nouns"]
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load noun cache: %s", exc)
            return False

    def _save_cache(self, cache_path: Path) -> None:
        try:
            payload = {
                "version": _NOUN_CACHE_VERSION,
                "nouns": self._nouns,
                "english_to_nouns": self._english_to_nouns,
            }
            with open(cache_path, "wb") as fh:
                pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not save noun cache: %s", exc)

    def _load_file(self, path: Path) -> None:
        import re  # noqa: PLC0415

        try:
            content = path.read_text(encoding="utf-8-sig", errors="replace")
            for line in content.splitlines():
                line = line.strip()
                if not line or line.isdigit():
                    continue
                if "/" not in line:
                    continue

                parts = line.split("/", 1)
                mlt = parts[0].strip().lower()
                # Normalize curly apostrophes for noun surfaces
                mlt = mlt.replace("ʼ", "'").replace("’", "'").replace("‘", "'").replace("ʻ", "'").replace("´", "'")
                rest = parts[1].strip()
                if "-" not in rest:
                    continue

                subparts = rest.split("-", 1)
                tag = subparts[0].strip().upper()
                gloss = subparts[1].strip().lower()

                gender = None
                if "SINGNOUNF" in tag:
                    gender = "F"
                elif "SINGNOUNM" in tag:
                    gender = "M"

                if gender:
                    self._nouns[mlt] = gender
                    for g in re.split(r"[;,]+", gloss):
                        g = g.strip()
                        if g.startswith("a "):
                            g = g[2:]
                        elif g.startswith("an "):
                            g = g[3:]
                        g = g.strip()
                        if g:
                            if g not in self._english_to_nouns:
                                self._english_to_nouns[g] = []
                            self._english_to_nouns[g].append((mlt, gender))
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to load noun file %s: %s", path, exc)

    def get_gender(self, mlt_word: str) -> str | None:
        self.load()
        return self._nouns.get(mlt_word.lower())

    def lookup_by_english(self, eng_lemma: str) -> list[tuple[str, str]]:
        self.load()
        return self._english_to_nouns.get(eng_lemma.lower(), [])


# Singleton instance accessors
_db_instance: LexiconDatabase | None = None
_noun_db_instance: NounDatabase | None = None


def get_lexicon_db(finaldics_dir: Path | None = None) -> LexiconDatabase:
    global _db_instance
    if _db_instance is None:
        _db_instance = LexiconDatabase(finaldics_dir)
        _db_instance.load()
    return _db_instance


def get_noun_db(finaldics_dir: Path | None = None) -> NounDatabase:
    global _noun_db_instance
    if _noun_db_instance is None:
        _noun_db_instance = NounDatabase(finaldics_dir)
        _noun_db_instance.load()
    return _noun_db_instance
