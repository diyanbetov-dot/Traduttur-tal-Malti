"""
translator_v2/candidates/corrections.py

Deterministic grammar and feature correction rules.
Applies corrections to neural candidates when validation flags specific errors
(e.g., verb person mismatches or spacing errors) and generates corrected candidate variants.
"""
from __future__ import annotations

import re

from translator_v2.maltese.lexicon.database import get_lexicon_db
from translator_v2.maltese.validation.agreement import _lemma_words, source_verb_lemmas
from translator_v2.result import TranslationCandidate, TranslationWarning
from translator_v2.source_analysis.models import ParsedSentence




BODY_PART_MAPPING = {
    "head": ("ras", "F"),
    "back": ("dahar", "M"),
    "arm": ("driegħ", "M"),
    "leg": ("sieq", "F"),
    "foot": ("sieq", "F"),
    "hand": ("id", "F"),
    "finger": ("saba'", "M"),
    "toe": ("saba'", "M"),
    "stomach": ("żaqq", "F"),
    "chest": ("sider", "M"),
    "neck": ("għonq", "M"),
    "throat": ("gerżuma", "F"),
    "ear": ("widna", "F"),
    "eye": ("għajn", "F"),
    "nose": ("mnieħer", "M"),
    "tooth": ("sinna", "F"),
    "teeth": ("snien", "P"),
    "heart": ("qalb", "F"),
}

POSS_CLITIC_MAPPING = {
    "my": "ni",
    "your": "k",
    "his": "h",
    "her": "ha",
    "our": "na",
    "their": "hom",
    "its": "h",
}


PHYSICAL_BREAK_SUBJECTS = {
    "glass", "window", "cup", "plate", "bottle", "chair", "table", "mirror", "vase",
    "dish", "bowl", "glassware", "pot", "plate", "brick", "stone", "bone", "branch",
}

BREAK_MAP = {
    "infirex": "inkiser",
    "infirxet": "inkisret",
    "infirxu": "inkisru",
}


def _correct_pain_idiom(text: str, eng_subj_lemma: str, eng_poss_lemma: str) -> str:
    gender = "M"
    if eng_subj_lemma in BODY_PART_MAPPING:
        gender = BODY_PART_MAPPING[eng_subj_lemma][1]

    clitic = POSS_CLITIC_MAPPING.get(eng_poss_lemma, "ni")

    if gender == "F":
        target_verb = f"qed tuġa{clitic}"
    else:
        target_verb = f"qed juġa{clitic}"

    # General pattern matching pain verbs with any potential apostrophe
    pain_verb_pattern = re.compile(
        r"\b(?:qed\s+)?(?:tweġġa|tuġa|weġġa|weġġgħet|weġġgħu|juġa|weġa|uġa)[’'ʼʻ´`‘]?\b",
        re.IGNORECASE,
    )

    corrected, count = pain_verb_pattern.subn(target_verb, text)
    if count == 0:
        if f"qed tuġa{clitic}" not in text and f"qed juġa{clitic}" not in text:
            corrected = f"{text} ({target_verb})"
    return corrected


def _source_matched_paradigms(paradigms, sentence: ParsedSentence):
    """Keep only paradigms whose English gloss loosely matches a source verb lemma."""
    if not sentence.parser_available:
        return list(paradigms)
    source_lemmas = source_verb_lemmas(sentence)
    if not source_lemmas:
        return []
    return [p for p in paradigms if _lemma_words(p.lemma) & source_lemmas]


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

    # 1. Bodily Pain Idiom Correction
    if sentence.parser_available:
        pain_verbs = [t for t in sentence.tokens if t.upos == "VERB" and t.lemma.lower() in {"hurt", "ache"}]
        for verb_tok in pain_verbs:
            subjs = [t for t in sentence.tokens if t.dep in {"nsubj", "nsubjpass"} and t.head_i == verb_tok.i]
            if subjs:
                subj_tok = subjs[0]
                subj_lemma = subj_tok.lemma.lower()
                if subj_lemma in BODY_PART_MAPPING:
                    poss_toks = [t for t in sentence.tokens if t.dep == "poss" and t.head_i == subj_tok.i]
                    poss_lemma = poss_toks[0].lemma.lower() if poss_toks else "my"
                    new_text = _correct_pain_idiom(text, subj_lemma, poss_lemma)
                    if new_text != text:
                        text = new_text
                        corrections_applied.append(f"corrected physical sensation idiom for {subj_lemma} ({poss_lemma})")

    # 2. Physical Break Word Sense Selection Correction
    if sentence.parser_available:
        break_verbs = [t for t in sentence.tokens if t.upos == "VERB" and t.lemma.lower() == "break"]
        for verb_tok in break_verbs:
            subjs = [t for t in sentence.tokens if t.dep in {"nsubj", "nsubjpass"} and t.head_i == verb_tok.i]
            if subjs:
                subj_tok = subjs[0]
                if subj_tok.lemma.lower() in PHYSICAL_BREAK_SUBJECTS:
                    for src_word, target_word in BREAK_MAP.items():
                        pattern = re.compile(rf"\b{re.escape(src_word)}[’'ʼʻ´`‘]?\b", re.IGNORECASE)
                        new_text, count = pattern.subn(target_word, text)
                        if count > 0:
                            text = new_text
                            corrections_applied.append(f"corrected physical breaking verb '{src_word}' to '{target_word}' for subject '{subj_tok.lemma}'")

    # 3. Present Stative Progressive Correction (Adding 'qed')
    tense_warnings = [
        w for w in candidate.validation_warnings
        if w.code == "WRONG_TENSE_ASPECT" and "expected progressive marker" in w.message
    ]
    for w in tense_warnings:
        match = re.search(r"Stative present verb '(\w+)' expected", w.message)
        if match:
            verb = match.group(1)
            pattern = re.compile(rf"\b{re.escape(verb)}\b", re.IGNORECASE)
            def replace_with_qed(m):
                v = m.group(0)
                if v.isupper():
                    return f"QED {v}"
                if v[0].isupper():
                    return f"Qed {v.lower()}"
                return f"qed {v}"
            new_text = pattern.sub(replace_with_qed, text)
            if new_text != text:
                text = new_text
                corrections_applied.append(f"added progressive marker 'qed' to present stative verb '{verb}'")

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

        matched_paradigms = _source_matched_paradigms(paradigms, sentence)
        if not matched_paradigms:
            continue

        correct_surface = None
        for p in matched_paradigms:
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
