"""
translator_v2/maltese/validation/agreement.py

Validation rules for grammatical agreement.
"""
from __future__ import annotations

from translator_v2.maltese.lexicon.database import get_lexicon_db
from translator_v2.result import TranslationWarning
from translator_v2.source_analysis.models import ParsedSentence


NON_VERB_SURFACES = {
    "barra", "ġewwa", "fuq", "isfel", "hemm", "hawn", "illum", "għada", "lbieraħ",
    "ukoll", "ħafna", "aktar", "inqas", "biss", "diġà", "qatt", "dejjem",
}

# Maltese imperfective tense codes that indicate habitual/continuous present
# (used to detect tense mismatch when English is past simple)
_IMPERFECTIVE_TENSES = {"MPERF"}

# English auxiliary lemmas that make a past-tense verb into past continuous
# e.g. "was", "were" before a VerbForm=Part token → aspect is progressive
_PROGRESSIVE_AUXILIARIES = {"be", "was", "were"}


def _clean_word(word: str) -> str:
    return word.lower().strip().rstrip(".,?!;:")


def validate_coordination_agreement(
    maltese_text: str,
    sentence: ParsedSentence,
) -> list[TranslationWarning]:
    warnings: list[TranslationWarning] = []
    root = sentence.root_token
    if not root or root.upos != "VERB":
        return warnings

    coord_verbs = [
        t for t in sentence.tokens
        if t.upos == "VERB" and t.dep == "conj" and t.head_i == root.i
    ]
    if not coord_verbs:
        return warnings

    db = get_lexicon_db()
    verb_features: dict[str, list[str]] = {}
    for word in maltese_text.split():
        clean_word = _clean_word(word)
        if clean_word in NON_VERB_SURFACES:
            continue
        paradigms = db.lookup_verb(clean_word)
        if paradigms:
            verb_features[clean_word] = [p.person for p in paradigms]

    first_person_verbs = [w for w, feats in verb_features.items() if any(f.startswith("1") for f in feats)]
    third_person_verbs = [w for w, feats in verb_features.items() if any(f.startswith("3") for f in feats)]

    if first_person_verbs and third_person_verbs:
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
    warnings: list[TranslationWarning] = []
    db = get_lexicon_db()

    subj_tokens = sentence.subject_tokens
    if not subj_tokens:
        return warnings

    subj = subj_tokens[0]
    expected_person = "3SM"
    if subj.lemma == "she" or subj.morph.get("Gender") == "Fem":
        expected_person = "3SF"
    elif subj.lemma in {"i", "me"}:
        expected_person = "1S"
    elif subj.lemma == "we":
        expected_person = "1P"
    elif subj.lemma in {"they", "them"}:
        expected_person = "3P"
    elif subj.lemma == "you":
        expected_person = "2S"

    is_plural = subj.morph.get("Number") == "Plur"
    if is_plural and expected_person.startswith("3"):
        expected_person = "3P"

    source_words = {t.lemma.lower() for t in sentence.tokens}
    for word in maltese_text.split():
        clean_word = _clean_word(word)
        if clean_word in NON_VERB_SURFACES:
            continue
        if clean_word in {"ta", "ta'"} and "give" not in source_words:
            continue

        paradigms = db.lookup_verb(clean_word)
        if not paradigms:
            continue

        matching_feats = [p for p in paradigms if p.person == expected_person]
        if not matching_feats:
            all_person_tags = {p.person for p in paradigms}
            if "ACTPAR" in {p.tense for p in paradigms}:
                continue
            warnings.append(TranslationWarning(
                code="WRONG_VERB_PERSON",
                message=f"Verb '{clean_word}' features ({sorted(all_person_tags)}) do not match expected subject person '{expected_person}' (from English '{subj.text}').",
                severity="warning",
            ))
    return warnings


def validate_tense_aspect_agreement(
    maltese_text: str,
    sentence: ParsedSentence,
) -> list[TranslationWarning]:
    """
    Detect cases where OPUS-MT translated a past-simple English verb into a
    Maltese imperfective/habitual form (MPERF) when a perfective past (PERF)
    is grammatically required.

    Conservative rule — only fires when the English ROOT verb is unambiguously
    past simple:  Tense=Past + VerbForm=Fin and NOT progressive (Aspect != Prog).
    This avoids false positives for past-continuous ("was swimming"),
    past-perfect ("had gone"), or habitual past ("used to swim").
    """
    warnings: list[TranslationWarning] = []
    if not sentence.parser_available:
        return warnings

    # Find candidate root verbs that are unambiguously past simple
    past_simple_roots: list[str] = []
    for token in sentence.tokens:
        morph = token.morph
        if (
            token.upos == "VERB"
            and token.dep in {"ROOT", "conj"}            # main or coordinated verb
            and morph.get("Tense") == "Past"
            and morph.get("VerbForm") == "Fin"            # finite form (not participle)
            and morph.get("Aspect") != "Prog"            # exclude progressive
        ):
            past_simple_roots.append(token.lemma)

    if not past_simple_roots:
        return warnings

    # Scan Maltese candidate words against the lexicon.
    # Goal: detect whether any PERF verb in the candidate is a genuine action verb,
    # NOT the copula auxiliary "kien" (kont/kont/kienu etc.) that appears in
    # past-continuous constructions like "kont ngħum" (I was swimming).
    db = get_lexicon_db()
    candidate_words = [_clean_word(w) for w in maltese_text.split()]

    # Lemma strings that identify the Maltese copula verb.
    # A surface form is treated as copula-only if EVERY one of its paradigm
    # lemmas is in this set — forms like "kont" which are ambiguous between the
    # copula and "to know" have at least one non-copula lemma, so they too must
    # be excluded (otherwise they would incorrectly suppress the warning).
    _COPULA_LEMMAS = {"kien", "to be"}

    has_noncop_perf_verb = False
    mperf_only_verbs: list[str] = []

    for clean_word in candidate_words:
        if clean_word in NON_VERB_SURFACES:
            continue
        paradigms = db.lookup_verb(clean_word)
        if not paradigms:
            continue
        tenses = {p.tense for p in paradigms}
        lemmas = {p.lemma.lower() for p in paradigms}
        if "ACTPAR" in tenses:
            continue  # active participles are not inflected for tense
        if "PERF" in tenses:
            # Count as non-copula PERF only when NO lemma is the copula.
            # If even one lemma is a copula (e.g. "kont" = "to be" PERF 1S),
            # the surface is treated as a potential copula auxiliary and skipped.
            if lemmas.isdisjoint(_COPULA_LEMMAS):
                has_noncop_perf_verb = True
        elif tenses <= _IMPERFECTIVE_TENSES:
            mperf_only_verbs.append(clean_word)

    # Warn only when no non-copula PERF verb is found — meaning the whole
    # candidate is expressed in imperfective despite the source being past simple.
    if not has_noncop_perf_verb and mperf_only_verbs:
        for clean_word in mperf_only_verbs:
            warnings.append(TranslationWarning(
                code="WRONG_TENSE_ASPECT",
                message=(
                    f"Verb '{clean_word}' is imperfective (MPERF) and no main-action "
                    f"perfective verb was found in the candidate, but source has "
                    f"past-simple root(s): {past_simple_roots}. "
                    "Expected a perfective (PERF) form."
                ),
                severity="warning",
            ))
    return warnings
