"""
translator_v2/lexical_sense/models.py

Data models for lexical-sense records.
One SenseRecord describes one meaning of one English lemma.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


REVIEW_STATUSES = frozenset({"needs_human_review", "machine_suggested", "verified"})
CONFIDENCE_TYPES = frozenset({"deterministic", "heuristic", "machine_suggested"})
TRANSITIVITY_VALUES = frozenset({"transitive", "intransitive", "both", "unknown"})


@dataclass
class SenseRecord:
    """One semantic sense of one English lemma."""
    english_lemma: str
    sense_id: str                           # e.g. "run_manage"
    pos: str                                # "VERB", "NOUN", "ADJ", ...
    definition: str                         # Human-readable definition in English
    maltese_lemma: str | None               # None until human-verified
    maltese_construction: str | None        # "reflexive", "phrasal", "periphrastic", ...
    transitivity: str = "unknown"
    subject_semantic_classes: list[str] = field(default_factory=list)
    object_semantic_classes: list[str] = field(default_factory=list)
    dep_frame: list[str] = field(default_factory=list)          # ["nsubj", "dobj"]
    collocations: list[str] = field(default_factory=list)
    examples_en: list[str] = field(default_factory=list)
    source: str = "machine_suggested"
    review_status: str = "needs_human_review"
    confidence_type: str = "machine_suggested"

    def __post_init__(self) -> None:
        if self.review_status not in REVIEW_STATUSES:
            self.review_status = "needs_human_review"
        if self.confidence_type not in CONFIDENCE_TYPES:
            self.confidence_type = "machine_suggested"
        if self.transitivity not in TRANSITIVITY_VALUES:
            self.transitivity = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "english_lemma": self.english_lemma,
            "sense_id": self.sense_id,
            "pos": self.pos,
            "definition": self.definition,
            "maltese_lemma": self.maltese_lemma,
            "maltese_construction": self.maltese_construction,
            "transitivity": self.transitivity,
            "subject_semantic_classes": self.subject_semantic_classes,
            "object_semantic_classes": self.object_semantic_classes,
            "dep_frame": self.dep_frame,
            "collocations": self.collocations,
            "examples_en": self.examples_en,
            "source": self.source,
            "review_status": self.review_status,
            "confidence_type": self.confidence_type,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SenseRecord":
        return cls(
            english_lemma=d["english_lemma"],
            sense_id=d["sense_id"],
            pos=d.get("pos", "VERB"),
            definition=d.get("definition", ""),
            maltese_lemma=d.get("maltese_lemma"),
            maltese_construction=d.get("maltese_construction"),
            transitivity=d.get("transitivity", "unknown"),
            subject_semantic_classes=d.get("subject_semantic_classes", []),
            object_semantic_classes=d.get("object_semantic_classes", []),
            dep_frame=d.get("dep_frame", []),
            collocations=d.get("collocations", []),
            examples_en=d.get("examples_en", []),
            source=d.get("source", "machine_suggested"),
            review_status=d.get("review_status", "needs_human_review"),
            confidence_type=d.get("confidence_type", "machine_suggested"),
        )
