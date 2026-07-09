"""
tests/validation/test_coordination_agreement.py

Unit tests for subject-verb agreement across coordinated clauses.
"""
from __future__ import annotations

from translator_v2.maltese.validation.agreement import validate_coordination_agreement
from translator_v2.source_analysis.models import ParsedSentence, Token


def _make_verb(i: int, lemma: str, dep: str, head_i: int) -> Token:
    return Token(
        i=i, text=lemma, lemma=lemma, upos="VERB",
        morph={}, dep=dep, head_i=head_i,
        ner="", char_start=0, char_end=len(lemma)
    )


class TestCoordinationAgreement:
    def test_agreement_warning_raised_for_mismatch(self):
        # English: "I went [ROOT] and did [conj]" -> went (ROOT), did (conj)
        went = _make_verb(1, "go", "ROOT", 1)
        did = _make_verb(2, "do", "conj", 1)
        sentence = ParsedSentence(text="I went and did work.", tokens=[went, did], parser_available=True)

        # Mismatched Maltese: "mort" (1S) vs "għamlet" (3SF)
        warnings = validate_coordination_agreement("Illum mort l-iskola u għamlet ftit xogħol.", sentence)
        assert len(warnings) == 1
        assert warnings[0].code == "WRONG_VERB_PERSON"

    def test_no_warning_for_correct_agreement(self):
        went = _make_verb(1, "go", "ROOT", 1)
        did = _make_verb(2, "do", "conj", 1)
        sentence = ParsedSentence(text="I went and did work.", tokens=[went, did], parser_available=True)

        # Correct Maltese: "mort" (1S) vs "għamilt" (1S)
        warnings = validate_coordination_agreement("Illum mort l-iskola u għamilt ftit xogħol.", sentence)
        assert len(warnings) == 0


def test_does_not_treat_barra_as_wrong_verb():
    from translator_v2.maltese.validation.agreement import validate_subject_verb_agreement
    from translator_v2.source_analysis.models import ParsedSentence, Token

    they = Token(i=0, text="They", lemma="they", upos="PRON", morph={"Number": "Plur"}, dep="nsubj", head_i=2, ner="", char_start=0, char_end=4)
    waiting = Token(i=2, text="waiting", lemma="wait", upos="VERB", morph={}, dep="ROOT", head_i=2, ner="", char_start=10, char_end=17)
    sentence = ParsedSentence(text="They were waiting outside.", tokens=[they, waiting], parser_available=True)

    warnings = validate_subject_verb_agreement("Huma kienu qed jistennew barra.", sentence)
    assert not [w for w in warnings if "barra" in w.message]

def test_source_verbs_gate_house_and_kif_homographs():
    from translator_v2.maltese.validation.agreement import validate_subject_verb_agreement
    from translator_v2.source_analysis.models import ParsedSentence, Token

    i = Token(i=0, text="I", lemma="i", upos="PRON", morph={}, dep="nsubj", head_i=2, ner="", char_start=0, char_end=1)
    know = Token(i=2, text="know", lemma="know", upos="VERB", morph={}, dep="ROOT", head_i=2, ner="", char_start=8, char_end=12)
    build = Token(i=5, text="build", lemma="build", upos="VERB", morph={}, dep="xcomp", head_i=2, ner="", char_start=20, char_end=25)
    house = Token(i=7, text="house", lemma="house", upos="NOUN", morph={}, dep="obj", head_i=5, ner="", char_start=28, char_end=33)
    sentence = ParsedSentence(text="I don't know how to build a house.", tokens=[i, know, build, house], parser_available=True)

    warnings = validate_subject_verb_agreement("Ma nafx kif nibni dar.", sentence)
    messages = "\n".join(w.message for w in warnings)
    assert "dar" not in messages
    assert "kif" not in messages