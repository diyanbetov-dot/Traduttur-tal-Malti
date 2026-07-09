"""
tests/lexicon/test_orthography.py

Unit tests for final Maltese orthographic autocorrections.
"""
from __future__ import annotations

from translator_v2.maltese.orthography import apply_final_orthography


def test_yesterday_exception_gets_initial_i_at_sentence_start_and_after_consonant():
    assert apply_final_orthography("Lbieraħ mort ngħum.") == "Ilbieraħ mort ngħum."
    assert apply_final_orthography("mort lbieraħ.") == "mort ilbieraħ."


def test_yesterday_exception_does_not_get_initial_i_after_vowel():
    assert apply_final_orthography("sa lbieraħ.") == "sa lbieraħ."


def test_general_initial_i_is_limited_to_repeated_initial_consonants():
    assert apply_final_orthography("Ktieb ġdid.") == "Ktieb ġdid."
    assert apply_final_orthography("dan ktieb.") == "dan ktieb."
    assert apply_final_orthography("Ddekorar ġdid.") == "Iddekorar ġdid."
    assert apply_final_orthography("mort wkoll.") == "mort wkoll."


def test_verb_initial_i_repeated_consonants_and_j_consonant_forms():
    assert apply_final_orthography("irid mmur.") == "irid immur."
    assert apply_final_orthography("Jmur illum.") == "Imur illum."
    assert apply_final_orthography("jmorru llum.") == "imorru llum."
    assert apply_final_orthography("trid tismaʼ.") == "trid tismaʼ."
    assert apply_final_orthography("Jien ħriġt.") == "Jien ħriġt."
    assert apply_final_orthography("mort ngħum.") == "mort ngħum."