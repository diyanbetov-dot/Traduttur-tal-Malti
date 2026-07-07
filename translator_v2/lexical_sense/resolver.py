"""
translator_v2/lexical_sense/resolver.py

Selects the most likely sense for a parsed English token given
the surrounding syntactic context.

Strategy:
1. Load all senses for the token's lemma from data/*.jsonl
2. Score each sense by matching:
   - transitivity against parsed deps
   - object semantic class against direct object token
   - subject semantic class against subject token
   - dep frame presence
   - collocations found in sentence
3. Return ranked list (best first)

Machine-suggested senses are returned as-is.
Maltese lemmas marked 'needs_human_review' must not be
automatically applied without user confirmation.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from translator_v2.lexical_sense.models import SenseRecord
from translator_v2.source_analysis.models import ParsedSentence, Token
from translator_v2.source_analysis.semantic_classes import UNKNOWN, NER_TO_SEMANTIC_CLASS, is_subclass

_DATA_DIR = Path(__file__).parent / "data"


@lru_cache(maxsize=128)
def _load_senses(lemma: str) -> list[SenseRecord]:
    """Load all senses for a lemma from its JSONL file (cached)."""
    path = _DATA_DIR / f"{lemma}.jsonl"
    if not path.exists():
        return []
    records: list[SenseRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(SenseRecord.from_dict(json.loads(line)))
        except (json.JSONDecodeError, KeyError):
            pass
    return records


def _object_semantic_class(token: Token, sentence: ParsedSentence) -> str:
    """Estimate semantic class of a token from NER or context."""
    if token.ner and token.ner in NER_TO_SEMANTIC_CLASS:
        return NER_TO_SEMANTIC_CLASS[token.ner]
    return UNKNOWN


def _score_sense(
    sense: SenseRecord,
    token: Token,
    sentence: ParsedSentence,
) -> float:
    """Return a heuristic score (higher = better match)."""
    score = 0.0

    # Transitivity match
    direct_objects = [t for t in sentence.tokens if t.dep in {"dobj", "obj"} and t.head_i == token.i]
    has_direct_object = bool(direct_objects)
    if sense.transitivity == "transitive" and has_direct_object:
        score += 3.0
    elif sense.transitivity == "intransitive" and not has_direct_object:
        score += 3.0
    elif sense.transitivity == "both":
        score += 1.0
    elif sense.transitivity == "transitive" and not has_direct_object:
        score -= 2.0
    elif sense.transitivity == "intransitive" and has_direct_object:
        score -= 2.0

    # Object semantic class match
    if direct_objects and sense.object_semantic_classes:
        obj_class = _object_semantic_class(direct_objects[0], sentence)
        if any(is_subclass(obj_class, req) for req in sense.object_semantic_classes):
            score += 4.0

    # Subject semantic class match
    subjects = [t for t in sentence.tokens if t.dep in {"nsubj", "nsubjpass"} and t.head_i == token.i]
    if subjects and sense.subject_semantic_classes:
        subj_class = _object_semantic_class(subjects[0], sentence)
        if any(is_subclass(subj_class, req) for req in sense.subject_semantic_classes):
            score += 2.0

    # Collocation match
    sentence_words = {t.lemma.lower() for t in sentence.tokens}
    colloc_hits = sum(
        1 for c in sense.collocations
        if any(w in c.lower() for w in sentence_words)
    )
    score += colloc_hits * 0.5

    # Dep frame match
    token_deps = {t.dep for t in sentence.tokens if t.head_i == token.i}
    token_deps.add(token.dep)
    frame_hits = sum(1 for dep in sense.dep_frame if dep in token_deps)
    score += frame_hits * 1.0

    return score


def resolve_senses(
    token: Token,
    sentence: ParsedSentence,
) -> list[SenseRecord]:
    """
    Return senses for token.lemma ranked by compatibility with the
    parsed sentence context. Empty if no senses are defined.
    """
    senses = _load_senses(token.lemma)
    if not senses:
        return []
    scored = [(_score_sense(s, token, sentence), s) for s in senses]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored]
