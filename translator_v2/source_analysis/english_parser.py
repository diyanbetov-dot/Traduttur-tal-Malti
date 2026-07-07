"""
translator_v2/source_analysis/english_parser.py

spaCy adapter for English dependency parsing.

Lazy loading: spaCy and the model are not imported at module level.
If spaCy is not installed, parse() returns a ParsedSentence with
parser_available=False and a PARSER_UNAVAILABLE warning.

Install:
    pip install spacy
    python -m spacy download en_core_web_sm
"""
from __future__ import annotations

import os
from functools import cached_property

from translator_v2.source_analysis.base import EnglishParser
from translator_v2.source_analysis.models import NamedEntity, ParsedSentence, Token


class SpacyParser(EnglishParser):
    """English parser backed by spaCy en_core_web_sm (or configured model)."""

    def __init__(self, model_name: str = "en_core_web_sm") -> None:
        self._model_name = model_name
        self._nlp = None
        self._load_error: str = ""

    def _ensure_loaded(self) -> bool:
        if self._nlp is not None:
            return True
        if self._load_error:
            return False
        try:
            import spacy  # noqa: PLC0415
            self._nlp = spacy.load(self._model_name)
            return True
        except ImportError:
            self._load_error = (
                "spaCy is not installed. "
                "Install with: pip install spacy && python -m spacy download en_core_web_sm"
            )
        except OSError:
            self._load_error = (
                f"spaCy model '{self._model_name}' not found. "
                f"Install with: python -m spacy download {self._model_name}"
            )
        return False

    @property
    def is_available(self) -> bool:
        return self._ensure_loaded()

    def parse(self, text: str) -> ParsedSentence:
        if not self._ensure_loaded():
            return ParsedSentence(
                text=text,
                tokens=[],
                entities=[],
                parser_available=False,
                warnings=[f"PARSER_UNAVAILABLE: {self._load_error}"],
            )

        doc = self._nlp(text)

        tokens: list[Token] = []
        for tok in doc:
            morph: dict[str, str] = {}
            for feat in str(tok.morph).split("|"):
                if "=" in feat:
                    k, v = feat.split("=", 1)
                    morph[k] = v

            tokens.append(Token(
                i=tok.i,
                text=tok.text,
                lemma=tok.lemma_.lower(),
                upos=tok.pos_,
                morph=morph,
                dep=tok.dep_,
                head_i=tok.head.i,
                ner=tok.ent_type_,
                char_start=tok.idx,
                char_end=tok.idx + len(tok.text),
            ))

        entities: list[NamedEntity] = [
            NamedEntity(
                text=ent.text,
                label=ent.label_,
                start_char=ent.start_char,
                end_char=ent.end_char,
            )
            for ent in doc.ents
        ]

        return ParsedSentence(
            text=text,
            tokens=tokens,
            entities=entities,
            parser_available=True,
            warnings=[],
        )


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_parser_instance: SpacyParser | None = None


def get_parser(model_name: str | None = None) -> SpacyParser:
    """Return a cached SpacyParser instance."""
    global _parser_instance
    if _parser_instance is None or (model_name and model_name != _parser_instance._model_name):
        _parser_instance = SpacyParser(model_name or os.getenv("SPACY_MODEL", "en_core_web_sm"))
    return _parser_instance
