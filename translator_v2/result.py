"""
translator_v2/result.py

Structured result models for the v2 translation pipeline.
These are independent of Flask and the legacy translator.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


VALID_WARNING_CODES = frozenset({
    "LEXICAL_SENSE",
    "UNKNOWN_WORD",
    "UNTRANSLATED_TOKEN",
    "WRONG_TENSE_ASPECT",
    "WRONG_VERB_PERSON",
    "WRONG_GENDER",
    "WRONG_NUMBER",
    "ARTICLE_ERROR",
    "PREPOSITION_ERROR",
    "CLITIC_ERROR",
    "NEGATION_ERROR",
    "WORD_ORDER",
    "IDIOM",
    "PHRASAL_VERB",
    "QUESTION_STRUCTURE",
    "RELATIVE_CLAUSE",
    "COORDINATION",
    "NAMED_ENTITY_ERROR",
    "NUMBER_PRESERVATION",
    "PUNCTUATION_ERROR",
    "HALLUCINATION",
    "MORPHOLOGY_INVALID",
    "TERMINOLOGY_ERROR",
    "PARSER_UNAVAILABLE",
    "BACKEND_UNAVAILABLE",
    "OTHER",
})

VALID_SEVERITIES = frozenset({"error", "warning", "info"})


@dataclass
class TranslationWarning:
    """A structured warning produced during translation analysis or validation."""
    code: str
    message: str
    severity: str = "warning"
    source_span: tuple[int, int] | None = None
    target_span: tuple[int, int] | None = None
    suggestions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.code not in VALID_WARNING_CODES:
            # Accept unknown codes but normalise to OTHER
            object.__setattr__(self, "code", "OTHER") if hasattr(self, "__dataclass_fields__") else None
        if self.severity not in VALID_SEVERITIES:
            self.severity = "warning"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "source_span": list(self.source_span) if self.source_span else None,
            "target_span": list(self.target_span) if self.target_span else None,
            "suggestions": self.suggestions,
        }


@dataclass
class TranslationCandidate:
    """A single translation candidate with full provenance."""
    text: str
    source: str
    model_score: float | None = None
    validation_warnings: list[TranslationWarning] = field(default_factory=list)
    applied_constraints: list[str] = field(default_factory=list)
    corrections: list[str] = field(default_factory=list)
    ranking_reasons: list[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for w in self.validation_warnings if w.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for w in self.validation_warnings if w.severity == "warning")

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "source": self.source,
            "model_score": self.model_score,
            "validation_warnings": [w.to_dict() for w in self.validation_warnings],
            "applied_constraints": self.applied_constraints,
            "corrections": self.corrections,
            "ranking_reasons": self.ranking_reasons,
        }


@dataclass
class TranslationResult:
    """Final result returned by the v2 engine."""
    source_text: str
    translated_text: str
    engine: str = "v2"
    backend: str | None = None
    alternatives: list[TranslationCandidate] = field(default_factory=list)
    warnings: list[TranslationWarning] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    latency_ms: float | None = None

    # Legacy compatibility fields — populated for Flask response
    @property
    def input(self) -> str:
        return self.source_text

    @property
    def direction(self) -> str:
        return self.metadata.get("direction", "en-mt")

    @property
    def candidates(self) -> list[dict[str, Any]]:
        return [c.to_dict() for c in self.alternatives]

    @property
    def notes(self) -> list[str]:
        return [w.message for w in self.warnings]

    def to_dict(self) -> dict[str, Any]:
        return {
            "input": self.source_text,
            "direction": self.direction,
            "translated_text": self.translated_text,
            "engine": self.engine,
            "backend": self.backend,
            "candidates": self.candidates,
            "warnings": [w.to_dict() for w in self.warnings],
            "notes": self.notes,
            "metadata": self.metadata,
            "latency_ms": self.latency_ms,
            "suggestions": [],
            "highlights": [],
        }
