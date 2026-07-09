"""
translator_v2/maltese/validation/agreement.py

Validation rules for grammatical agreement.
"""
from __future__ import annotations

import re

from translator_v2.maltese.lexicon.database import get_lexicon_db
from translator_v2.result import TranslationWarning
from translator_v2.source_analysis.models import ParsedSentence


NON_VERB_SURFACES = {
    "barra", "ġewwa", "fuq", "isfel", "hemm", "hawn", "illum", "għada", "lbieraħ",
    "ukoll", "ħafna", "aktar", "inqas", "biss", "diġà", "qatt", "dejjem",
}

_IMPERFECTIVE_TENSES = {"MPERF"}
_PROGRESSIVE_AUXILIARIES = {"be", "was", "were"}

FEMININE_NOUNS = {
    "girl", "woman", "mother", "sister", "daughter", "wife", "queen", "princess",
    "lady", "waitress", "actress", "cow", "hen", "cat", "dog"
}

STATIVE_VERBS = {
    "see", "hear", "understand", "know", "believe", "remember", "forget",
    "hurt", "ache", "pain", "shine", "glow", "rain", "snow", "feel", "like", "love"
}

HABITUAL_WORDS = {
    "always", "never", "often", "usually", "sometimes", "normally", "typically",
    "every", "daily", "weekly", "monthly", "yearly", "regularly"
}


def _clean_word(word: str) -> str:
    cleaned = word.lower().strip().rstrip(".,?!;:")
    # Replace curly apostrophes with straight ones for dictionary lookup consistency
    cleaned = cleaned.replace("ʼ", "'").replace("’", "'").replace("‘", "'").replace("ʻ", "'").replace("´", "'")
    return cleaned


def source_verb_lemmas(sentence: ParsedSentence) -> set[str]:
    """Return English source lemmas that can license Maltese verb correction."""
    if not sentence.parser_available:
        return set()
    blocked_aux = {"be", "do", "have"}
    lemmas: set[str] = set()
    for token in sentence.tokens:
        lemma = token.lemma.lower().strip()
        if not lemma:
            continue
        if token.upos == "VERB":
            lemmas.add(lemma)
        elif token.upos == "AUX" and lemma not in blocked_aux:
            lemmas.add(lemma)
    return lemmas


def _lemma_words(lemma: str) -> set[str]:
    cleaned = lemma.lower().strip()
    if cleaned.startswith("to "):
        cleaned = cleaned[3:]
    return {part for part in re.split(r"[^a-z]+", cleaned) if part and part not in {"to", "or", "and", "of", "sb"}}


def verb_features_match_source(features, sentence: ParsedSentence) -> bool:
    """True when a Maltese verb paradigm is compatible with a source English verb lemma."""
    source_lemmas = source_verb_lemmas(sentence)
    if not sentence.parser_available:
        return True
    if not source_lemmas:
        return False
    for feature in features:
        if _lemma_words(feature.lemma) & source_lemmas:
            return True
    return False


def _find_matching_english_verb(mlt_word_paradigms, sentence: ParsedSentence) -> Token | None:
    if not sentence.parser_available:
        return None
    source_lemmas = source_verb_lemmas(sentence)
    for p in mlt_word_paradigms:
        p_words = _lemma_words(p.lemma)
        for tok in sentence.tokens:
            if tok.upos in {"VERB", "AUX"} and tok.lemma.lower() in p_words:
                return tok
    return None


def _expected_person_for_verb(eng_tok: Token | None, sentence: ParsedSentence) -> str:
    if not eng_tok or not sentence.parser_available:
        return _resolve_main_subject_person(sentence)

    # 1. Look for direct subject child of the verb
    subj_tokens = [t for t in sentence.tokens if t.dep in {"nsubj", "nsubjpass", "csubj"} and t.head_i == eng_tok.i]

    # 2. If no subject child, and it is an xcomp (open clausal complement), find the parent verb
    if not subj_tokens and eng_tok.dep == "xcomp" and eng_tok.head_i < len(sentence.tokens):
        parent_tok = sentence.tokens[eng_tok.head_i]
        # Look for parent's object which acts as subject of the xcomp (e.g. "I want YOU to try")
        obj_tokens = [t for t in sentence.tokens if t.dep in {"dobj", "obj", "iobj"} and t.head_i == parent_tok.i]
        if obj_tokens:
            subj_tokens = [obj_tokens[0]]
        else:
            # Fall back to parent verb's subject
            subj_tokens = [t for t in sentence.tokens if t.dep in {"nsubj", "nsubjpass", "csubj"} and t.head_i == parent_tok.i]

    if not subj_tokens:
        return _resolve_main_subject_person(sentence)

    subj = subj_tokens[0]
    expected_person = "3SM"
    lemma = subj.lemma.lower()

    if lemma == "she" or subj.morph.get("Gender") == "Fem":
        expected_person = "3SF"
    elif lemma in {"i", "me"}:
        expected_person = "1S"
    elif lemma == "we":
        expected_person = "1P"
    elif lemma in {"they", "them"}:
        expected_person = "3P"
    elif lemma == "you":
        expected_person = "2S"
    elif subj.upos == "NOUN":
        # Check gender using fixednouns.dic
        from translator_v2.maltese.lexicon.database import get_noun_db  # noqa: PLC0415
        ndb = get_noun_db()
        mlt_nouns = ndb.lookup_by_english(subj.lemma)
        is_fem = False
        if mlt_nouns:
            is_fem = any(gender == "F" for _, gender in mlt_nouns)
        else:
            is_fem = lemma in FEMININE_NOUNS
        expected_person = "3SF" if is_fem else "3SM"

    is_plural = subj.morph.get("Number") == "Plur"
    if is_plural and expected_person.startswith("3"):
        expected_person = "3P"

    return expected_person


def _resolve_main_subject_person(sentence: ParsedSentence) -> str:
    subj_tokens = sentence.subject_tokens
    if not subj_tokens:
        return "3SM"
    subj = subj_tokens[0]
    expected_person = "3SM"
    lemma = subj.lemma.lower()
    if lemma == "she" or subj.morph.get("Gender") == "Fem":
        expected_person = "3SF"
    elif lemma in {"i", "me"}:
        expected_person = "1S"
    elif lemma == "we":
        expected_person = "1P"
    elif lemma in {"they", "them"}:
        expected_person = "3P"
    elif lemma == "you":
        expected_person = "2S"

    is_plural = subj.morph.get("Number") == "Plur"
    if is_plural and expected_person.startswith("3"):
        expected_person = "3P"
    return expected_person


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
        if paradigms and verb_features_match_source(paradigms, sentence):
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

    for word in maltese_text.split():
        clean_word = _clean_word(word)
        if clean_word in NON_VERB_SURFACES:
            continue
        if clean_word in {"ta", "ta'"}:
            source_words = {t.lemma.lower() for t in sentence.tokens}
            if "give" not in source_words:
                continue

        paradigms = db.lookup_verb(clean_word)
        if not paradigms:
            continue
        if not verb_features_match_source(paradigms, sentence):
            continue

        eng_tok = _find_matching_english_verb(paradigms, sentence)
        expected_person = _expected_person_for_verb(eng_tok, sentence)

        matching_feats = [p for p in paradigms if p.person == expected_person]
        if not matching_feats:
            all_person_tags = {p.person for p in paradigms}
            if "ACTPAR" in {p.tense for p in paradigms}:
                continue
            warnings.append(TranslationWarning(
                code="WRONG_VERB_PERSON",
                message=f"Verb '{clean_word}' features ({sorted(all_person_tags)}) do not match expected subject person '{expected_person}'.",
                severity="warning",
            ))
    return warnings


def validate_tense_aspect_agreement(
    maltese_text: str,
    sentence: ParsedSentence,
) -> list[TranslationWarning]:
    warnings: list[TranslationWarning] = []
    if not sentence.parser_available:
        return warnings

    db = get_lexicon_db()
    candidate_words = [_clean_word(w) for w in maltese_text.split()]
    _COPULA_LEMMAS = {"kien", "to be"}

    # We determine the expected aspect/tense per verb token in the sentence
    for token in sentence.tokens:
        if token.upos != "VERB" or token.dep not in {"ROOT", "conj", "xcomp", "ccomp"}:
            continue

        # 1. Determine English clause tense/aspect
        morph = token.morph
        is_past = morph.get("Tense") == "Past"

        # Look for auxiliary "did" to identify past simple negatives
        has_past_do = False
        for child in sentence.tokens:
            if child.head_i == token.i and child.upos == "AUX" and child.lemma.lower() == "do" and child.morph.get("Tense") == "Past":
                has_past_do = True
                break

        is_past_simple = (is_past and morph.get("Aspect") != "Prog") or has_past_do
        is_past_progressive = is_past and morph.get("Aspect") == "Prog"

        # Check if the English verb has a past "be" auxiliary (like "was swimming")
        for child in sentence.tokens:
            if child.head_i == token.i and child.upos == "AUX" and child.lemma.lower() in {"be", "was", "were"} and child.morph.get("Tense") == "Past":
                is_past_progressive = True
                is_past_simple = False
                break

        is_present = morph.get("Tense") == "Pres"
        is_stative = token.lemma.lower() in STATIVE_VERBS

        # Check if the sentence has any habitual adverbs
        sentence_lemmas = {t.lemma.lower() for t in sentence.tokens}
        has_habitual = bool(sentence_lemmas & HABITUAL_WORDS)

        # 2. Match candidate Maltese verbs for this English token
        matching_mlt_verbs = []
        for word in candidate_words:
            paradigms = db.lookup_verb(word)
            if not paradigms:
                continue
            # Keep only paradigms matching this specific token's lemma
            if any(token.lemma.lower() in _lemma_words(p.lemma) for p in paradigms):
                matching_mlt_verbs.append((word, paradigms))

        if not matching_mlt_verbs:
            continue

        # 3. Validate aspectual requirements
        if is_past_progressive:
            # Mandate past progressive: candidate should contain a past copula verb ("kont", "kien")
            # and an imperfective main verb.
            has_copula = any(w in {"kont", "kien", "kienet", "kienu", "konna", "kontu"} for w in candidate_words)
            if not has_copula:
                for word, paradigms in matching_mlt_verbs:
                    warnings.append(TranslationWarning(
                        code="WRONG_TENSE_ASPECT",
                        message=f"Verb '{word}' expected past progressive aspect ('kont qed + verb'), but no past copula auxiliary ('kont'/'kien') was found.",
                        severity="warning",
                    ))
        elif is_present and is_stative and not has_habitual:
            # Mandate progressive aspect (qed) for current state/sensation
            has_qed = any(w in {"qed", "qiegħed", "qiegħda", "qegħdin"} for w in candidate_words)
            if not has_qed:
                for word, paradigms in matching_mlt_verbs:
                    warnings.append(TranslationWarning(
                        code="WRONG_TENSE_ASPECT",
                        message=f"Stative present verb '{word}' expected progressive marker ('qed') for current state, but none was found.",
                        severity="warning",
                    ))
        elif is_past_simple:
            # Mandate perfective past (PERF) and reject MPERF unless copula
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
                    continue
                if "PERF" in tenses:
                    if lemmas.isdisjoint(_COPULA_LEMMAS):
                        has_noncop_perf_verb = True
                elif tenses <= _IMPERFECTIVE_TENSES:
                    # Only collect it if it matches this past simple token
                    if any(token.lemma.lower() in _lemma_words(p.lemma) for p in paradigms):
                        mperf_only_verbs.append(clean_word)

            if not has_noncop_perf_verb and mperf_only_verbs:
                for clean_word in mperf_only_verbs:
                    warnings.append(TranslationWarning(
                        code="WRONG_TENSE_ASPECT",
                        message=(
                            f"Verb '{clean_word}' is imperfective (MPERF) and no main-action "
                            f"perfective verb was found in the candidate, but source has past-simple verb '{token.lemma}'. "
                            "Expected a perfective (PERF) form."
                        ),
                        severity="warning",
                    ))

    return warnings


def validate_vocabulary_senses(
    maltese_text: str,
    sentence: ParsedSentence,
) -> list[TranslationWarning]:
    warnings: list[TranslationWarning] = []
    if not sentence.parser_available:
        return warnings

    candidate_words = [_clean_word(w) for w in maltese_text.split()]

    # 1. Break polysemy check
    break_verbs = [t for t in sentence.tokens if t.upos == "VERB" and t.lemma.lower() == "break"]
    for verb_tok in break_verbs:
        subjs = [t for t in sentence.tokens if t.dep in {"nsubj", "nsubjpass"} and t.head_i == verb_tok.i]
        if subjs:
            subj_tok = subjs[0]
            from translator_v2.candidates.corrections import PHYSICAL_BREAK_SUBJECTS, BREAK_MAP  # noqa: PLC0415
            if subj_tok.lemma.lower() in PHYSICAL_BREAK_SUBJECTS:
                # If candidate uses any metaphorical break word (infirex, infirxet, infirxu), warn!
                for word in candidate_words:
                    if word in BREAK_MAP:
                        warnings.append(TranslationWarning(
                            code="WRONG_VOCAB_SENSE",
                            message=f"Verb '{word}' is a metaphorical translation of 'break' (to spread), but subject '{subj_tok.lemma}' is a physical object. Expected a physical breaking verb (e.g. 'inkiser').",
                            severity="warning"
                        ))
    return warnings
