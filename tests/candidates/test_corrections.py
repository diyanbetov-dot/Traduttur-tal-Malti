"""
tests/candidates/test_corrections.py

Unit tests for candidate grammar corrections.
"""
from __future__ import annotations

from translator_v2.candidates.corrections import apply_candidate_corrections
from translator_v2.result import TranslationCandidate, TranslationWarning
from translator_v2.source_analysis.models import ParsedSentence, Token


def _make_verb(i: int, lemma: str, dep: str, head_i: int) -> Token:
    return Token(
        i=i, text=lemma, lemma=lemma, upos="VERB",
        morph={}, dep=dep, head_i=head_i,
        ner="", char_start=0, char_end=len(lemma)
    )


class TestCandidateCorrections:
    def test_corrects_verb_person_mismatch(self):
        # English: "she went" -> subject "she" (3SF)
        she = Token(
            i=0, text="she", lemma="she", upos="PRON",
            morph={"Gender": "Fem", "Number": "Sing"}, dep="nsubj", head_i=1,
            ner="", char_start=0, char_end=3
        )
        went = _make_verb(1, "go", "ROOT", 1)
        sentence = ParsedSentence(text="She went to school.", tokens=[she, went], parser_available=True)

        # Candidate with wrong verb: "marru" (3P)
        candidate = TranslationCandidate(
            text="Illum hi marru l-iskola.",
            source="opus_mt",
            model_score=-1.0,
            validation_warnings=[
                TranslationWarning(
                    code="WRONG_VERB_PERSON",
                    message="Verb 'marru' features (['3P']) do not match expected subject person '3SF' (from English 'she').",
                )
            ]
        )

        corrected = apply_candidate_corrections(candidate, sentence)
        assert len(corrected) == 1
        assert "marret" in corrected[0].text
        assert "hi marret" in corrected[0].text.lower()
        assert corrected[0].corrections[0] == "corrected verb 'marru' to 'marret'"
