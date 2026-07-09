from __future__ import annotations

from translator_v2.configuration import V2Config
from translator_v2.pipeline import TranslationPipeline
from translator_v2.result import TranslationCandidate
from translator_v2.source_analysis.models import ParsedSentence, Token


def test_go_gerund_prefers_go_activity_candidate_and_normalizes_yesterday():
    pipeline = TranslationPipeline(V2Config(backend="rules", preload_spacy=False, preload_opus=False))
    i = Token(i=0, text="I", lemma="i", upos="PRON", morph={}, dep="nsubj", head_i=1, ner="", char_start=0, char_end=1)
    went = Token(i=1, text="went", lemma="go", upos="VERB", morph={"Tense": "Past", "VerbForm": "Fin"}, dep="ROOT", head_i=1, ner="", char_start=2, char_end=6)
    swimming = Token(i=2, text="swimming", lemma="swim", upos="VERB", morph={"VerbForm": "Part"}, dep="xcomp", head_i=1, ner="", char_start=7, char_end=15)
    sentence = ParsedSentence(text="I went swimming yesterday.", tokens=[i, went, swimming], parser_available=True)
    candidates = [
        TranslationCandidate(text="Bieraħ bdejt ngħum.", source="opus_mt", model_score=-0.1),
        TranslationCandidate(text="Bieraħ mort ngħum.", source="opus_mt", model_score=-0.5),
    ]

    ranked = pipeline._rerank(candidates, constraints=None, sentence=sentence)
    assert ranked[0].text == "Bieraħ mort ngħum."
    assert pipeline._post_process_clean(ranked[0].text, sentence.text) == "Ilbieraħ mort ngħum."