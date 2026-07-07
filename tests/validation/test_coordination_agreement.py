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
