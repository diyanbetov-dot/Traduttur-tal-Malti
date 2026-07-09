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


def test_corrects_homograph_using_source_verb_gloss():
    from translator_v2.candidates.corrections import apply_candidate_corrections
    from translator_v2.result import TranslationCandidate, TranslationWarning
    from translator_v2.source_analysis.models import ParsedSentence, Token

    i = Token(i=0, text="I", lemma="i", upos="PRON", morph={}, dep="nsubj", head_i=1, ner="", char_start=0, char_end=1)
    went = Token(i=1, text="went", lemma="go", upos="VERB", morph={"Tense": "Past", "VerbForm": "Fin"}, dep="ROOT", head_i=1, ner="", char_start=2, char_end=6)
    sentence = ParsedSentence(text="I went.", tokens=[i, went], parser_available=True)
    candidate = TranslationCandidate(
        text="I marru.",
        source="opus_mt",
        model_score=-1.0,
        validation_warnings=[TranslationWarning(
            code="WRONG_VERB_PERSON",
            message="Verb 'marru' features (['2P', '3P']) do not match expected subject person '1S' (from English 'I').",
        )],
    )

    corrected = apply_candidate_corrections(candidate, sentence)
    assert corrected
    assert corrected[0].text == "I mort."
    assert "marrart" not in corrected[0].text