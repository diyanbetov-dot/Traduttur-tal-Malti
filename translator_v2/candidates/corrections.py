"""
translator_v2/candidates/corrections.py

Deterministic grammar and feature correction rules.
Applies corrections to neural candidates when validation flags specific errors
(e.g., verb person mismatches or spacing errors) and generates corrected candidate variants.
"""
from __future__ import annotations

import re

from translator_v2.maltese.lexicon.database import get_lexicon_db
from translator_v2.result import TranslationCandidate, TranslationWarning
from translator_v2.source_analysis.models import ParsedSentence


def apply_candidate_corrections(
    candidate: TranslationCandidate,
    sentence: ParsedSentence,
) -> list[TranslationCandidate]:
    """
    Inspect validation warnings on a candidate. If correctable errors are found
    (like verb person mismatch), generate and return one or more corrected candidate variants.
    """
    corrections_applied: list[str] = []
    text = candidate.text
    db = get_lexicon_db()

    # Look for WRONG_VERB_PERSON warnings
    verb_mismatch_warnings = [
        w for w in candidate.validation_warnings
        if w.code == "WRONG_VERB_PERSON"
    ]

    for w in verb_mismatch_warnings:
        # Extract the wrong verb name from the warning message
        # e.g., "Verb 'marru' features (['3P']) do not match expected subject person '3SF'"
        match = re.search(r"Verb '(\w+)' features", w.message)
        if not match:
            continue
        wrong_verb = match.group(1)

        # Extract the expected person
        match_person = re.search(r"expected subject person '(\w+)'", w.message)
        if not match_person:
            continue
        expected_person = match_person.group(1)

        # Find the lemma of the wrong verb in our database
        paradigms = db.lookup_verb(wrong_verb)
        if not paradigms:
            continue

        correct_surface = None
        for p in paradigms:
            # Find the correct surface form for this lemma + tense + expected person
            correct_surface = db.find_verb_surface(p.lemma, p.tense, expected_person, p.negative)
            if correct_surface and correct_surface.lower() != wrong_verb.lower():
                break

        if correct_surface and correct_surface.lower() != wrong_verb.lower():
            # Apply the replacement (preserving casing)
            pattern = re.compile(rf"\b{re.escape(wrong_verb)}\b", re.IGNORECASE)
            def replace(m: re.Match) -> str:
                v = m.group(0)
                if v.isupper():
                    return correct_surface.upper()
                if v[0].isupper():
                    return correct_surface[0].upper() + correct_surface[1:]
                return correct_surface

            new_text = pattern.sub(replace, text)
            if new_text != text:
                text = new_text
                corrections_applied.append(f"corrected verb '{wrong_verb}' to '{correct_surface}'")

    if corrections_applied:
        # Create a new corrected candidate variant
        corrected_candidate = TranslationCandidate(
            text=text,
            source=f"{candidate.source}+corrections",
            model_score=(candidate.model_score or 0.0) - 0.05, # minor penalty so raw correct is preferred if available
            applied_constraints=list(candidate.applied_constraints),
            corrections=corrections_applied,
        )
        return [corrected_candidate]

    return []
