"""
translator_v2/source_analysis/models.py

Data models for parsed English sentences.
No NLP library is imported here — these are pure data containers.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Token:
    """A single token from the English parser."""
    i: int                  # Position index in sentence
    text: str               # Original surface form
    lemma: str              # Dictionary/base form
    upos: str               # Universal POS tag (NOUN, VERB, ADJ, ADV, ADP, PRON, DET, ...)
    morph: dict[str, str]   # Morphological features: {"Tense": "Past", "Number": "Sing", ...}
    dep: str                # Dependency relation (nsubj, dobj, amod, ...)
    head_i: int             # Index of syntactic head
    ner: str                # Named entity type ("", "PERSON", "ORG", "GPE", ...)
    char_start: int         # Character start offset in original text
    char_end: int           # Character end offset in original text

    @property
    def is_subject(self) -> bool:
        return self.dep in {"nsubj", "nsubjpass", "csubj"}

    @property
    def is_direct_object(self) -> bool:
        return self.dep in {"dobj", "obj", "pobj"}

    @property
    def is_negation(self) -> bool:
        return self.dep == "neg"

    @property
    def is_auxiliary(self) -> bool:
        return self.dep in {"aux", "auxpass"}

    @property
    def is_root(self) -> bool:
        return self.dep == "ROOT"


@dataclass
class NamedEntity:
    text: str
    label: str      # PERSON, ORG, GPE, DATE, TIME, CARDINAL, etc.
    start_char: int
    end_char: int


@dataclass
class ParsedSentence:
    """The result of parsing one English sentence."""
    text: str
    tokens: list[Token] = field(default_factory=list)
    entities: list[NamedEntity] = field(default_factory=list)
    parser_available: bool = True
    warnings: list[str] = field(default_factory=list)

    @property
    def root_token(self) -> Token | None:
        for t in self.tokens:
            if t.is_root:
                return t
        return None

    @property
    def subject_tokens(self) -> list[Token]:
        return [t for t in self.tokens if t.is_subject]

    @property
    def direct_object_tokens(self) -> list[Token]:
        return [t for t in self.tokens if t.is_direct_object]

    def get_children(self, head_i: int) -> list[Token]:
        return [t for t in self.tokens if t.head_i == head_i and t.i != head_i]

    def get_token(self, i: int) -> Token | None:
        for t in self.tokens:
            if t.i == i:
                return t
        return None
