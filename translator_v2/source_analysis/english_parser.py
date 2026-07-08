"""
translator_v2/source_analysis/english_parser.py

Thread-safe spaCy adapter for English dependency parsing.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass

from translator_v2.source_analysis.base import EnglishParser
from translator_v2.source_analysis.models import NamedEntity, ParsedSentence, Token


@dataclass(frozen=True)
class ParserStatus:
    ready: bool
    model: str
    load_error: str
    load_ms: float | None


class SpacyParser(EnglishParser):
    """English parser backed by a cached spaCy Language instance."""

    def __init__(self, model_name: str = "en_core_web_sm") -> None:
        self._model_name = model_name
        self._nlp = None
        self._load_error = ""
        self._load_ms: float | None = None
        self._lock = threading.Lock()

    def initialize(self, *, required: bool = False) -> ParserStatus:
        if self._nlp is not None:
            return self.status
        if self._load_error:
            if required:
                raise RuntimeError(self._load_error)
            return self.status

        with self._lock:
            if self._nlp is not None or self._load_error:
                if required and self._load_error:
                    raise RuntimeError(self._load_error)
                return self.status
            started = time.perf_counter()
            try:
                import spacy  # noqa: PLC0415
                self._nlp = spacy.load(self._model_name)
                self._load_ms = (time.perf_counter() - started) * 1000
            except ImportError as exc:
                self._load_error = (
                    "spaCy is not installed. Install spacy and the configured English model."
                )
                self._load_ms = (time.perf_counter() - started) * 1000
                if required:
                    raise RuntimeError(self._load_error) from exc
            except OSError as exc:
                self._load_error = f"spaCy model '{self._model_name}' is not installed."
                self._load_ms = (time.perf_counter() - started) * 1000
                if required:
                    raise RuntimeError(self._load_error) from exc
        return self.status

    @property
    def status(self) -> ParserStatus:
        return ParserStatus(
            ready=self._nlp is not None,
            model=self._model_name,
            load_error=self._load_error,
            load_ms=self._load_ms,
        )

    @property
    def is_available(self) -> bool:
        return self.initialize(required=False).ready

    def parse(self, text: str) -> ParsedSentence:
        if not self.initialize(required=False).ready:
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

        entities = [
            NamedEntity(
                text=ent.text,
                label=ent.label_,
                start_char=ent.start_char,
                end_char=ent.end_char,
            )
            for ent in doc.ents
        ]
        return ParsedSentence(text=text, tokens=tokens, entities=entities, parser_available=True, warnings=[])


_parser_instance: SpacyParser | None = None
_parser_lock = threading.Lock()


def get_parser(model_name: str | None = None) -> SpacyParser:
    """Return a cached parser instance for the requested model."""
    global _parser_instance
    requested = model_name or os.getenv("SPACY_MODEL", "en_core_web_sm")
    with _parser_lock:
        if _parser_instance is None or requested != _parser_instance._model_name:
            _parser_instance = SpacyParser(requested)
        return _parser_instance
