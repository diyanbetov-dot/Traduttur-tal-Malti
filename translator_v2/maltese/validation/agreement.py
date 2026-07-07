"""
translator_v2/maltese/validation/agreement.py

Validation rules for grammatical agreement (Subject-Verb, Gender/Number, Coordination).
"""
from __future__ import annotations

from translator_v2.maltese.lexicon.database import get_lexicon_db
from translator_v2.result import TranslationWarning
from translator_v2.source_analysis.models import ParsedSentence


def validate_coordination_agreement(
    maltese_text: str,
    sentence: ParsedSentence,
) -> list[TranslationWarning]:
    """
    Verify that verbs in coordinated clauses agree in person and number.
    If the English source uses coordinated verbs sharing a subject (e.g. 'I went ... and did'),
    we check if the Maltese translation has mismatched verb forms (e.g. 'mort' [1S] vs 'għamlet' [3SF]).
    """
    warnings: list[TranslationWarning] = []

    # Find the main subject pronoun or noun
    root = sentence.root_token
    if not root or root.upos != "VERB":
        return warnings

    # Find coordinated verbs that share the same subject
    coord_verbs = [
        t for t in sentence.tokens
        if t.upos == "VERB" and t.dep == "conj" and t.head_i == root.i
    ]

    if not coord_verbs:
        return warnings

    # Match common surface patterns via coordination check
    text_lower = maltese_text.lower()
    words = text_lower.split()

    db = get_lexicon_db()

    # Look up verb surface forms in the translated text to extract their feature markers
    verb_features: dict[str, list[str]] = {}
    for word in words:
        clean_word = word.rstrip(".,?!")
        paradigms = db.lookup_verb(clean_word)
        if paradigms:
            # Gather all possible person tags (e.g. 1S, 3SF, 3P)
            verb_features[clean_word] = [p.person for p in paradigms]

    # Find candidate verbs in the text matching the English root verb glosses
    # Simple check: if we see 'mort' (1S) and 'għamlet' (3SF/3SM), flag coordination mismatch
    first_person_verbs = [w for w, feats in verb_features.items() if any(f.startswith("1") for f in feats)]
    third_person_verbs = [w for w, feats in verb_features.items() if any(f.startswith("3") for f in feats)]

    if first_person_verbs and third_person_verbs:
        # Avoid false positives if the sentence has multiple clauses with different subjects
        # but here we know the English structure shares the subject.
        warnings.append(TranslationWarning(
            code="WRONG_VERB_PERSON",
            message=f"Coordination mismatch: found mismatched verb agreements '{first_person_verbs[0]}' and '{third_person_verbs[0]}'. Verb persons must match.",
            severity="warning",
        ))

    return warnings


def validate_subject_verb_agreement(
    maltese_text: str,
    sentence: ParsedSentence,
) -> list[TranslationWarning]:
    """
    Verify that the main verbs agree with the English subject.
    E.g. English 'she went' (3SF) -> Maltese 'marret' (3SF), not 'marru' (3P).
    """
    warnings: list[TranslationWarning] = []
    db = get_lexicon_db()

    # 1. Identify English subject person features
    subj_tokens = sentence.subject_tokens
    if not subj_tokens:
        return warnings

    subj = subj_tokens[0]
    expected_person = "3SM"  # default
    if subj.lemma == "she" or subj.morph.get("Gender") == "Fem":
        expected_person = "3SF"
    elif subj.lemma in {"i", "me"}:
        expected_person = "1S"
    elif subj.lemma == "we":
        expected_person = "1P"
    elif subj.lemma in {"they", "them"}:
        expected_person = "3P"
    elif subj.lemma == "you":
        expected_person = "2S"  # default to 2S

    # Check if number is plural
    is_plural = subj.morph.get("Number") == "Plur"
    if is_plural and expected_person.startswith("3"):
        expected_person = "3P"

    # 2. Extract Maltese verbs in candidate text
    words = maltese_text.lower().split()
    for word in words:
        clean_word = word.rstrip(".,?!")
        if clean_word in {"ta", "ta'"}:
            # Skip if "give" is not in the English source
            source_words = {t.lemma.lower() for t in sentence.tokens}
            if "give" not in source_words:
                continue

        paradigms = db.lookup_verb(clean_word)
        if not paradigms:
            continue

        # Check if the verb paradigms match the expected subject features
        # Ignore tense for this check
        matching_feats = [p for p in paradigms if p.person == expected_person]
        if not matching_feats:
            # We found a verb, but none of its entries match the subject's person/gender/number
            # Flag a warning so this candidate is downranked.
            all_person_tags = {p.person for p in paradigms}
            # Skip common false positives (e.g. passive participles or irregulars)
            if "ACTPAR" in {p.tense for p in paradigms}:
                continue
            warnings.append(TranslationWarning(
                code="WRONG_VERB_PERSON",
                message=f"Verb '{clean_word}' features ({sorted(all_person_tags)}) do not match expected subject person '{expected_person}' (from English '{subj.text}').",
                severity="warning",
            ))

    return warnings
