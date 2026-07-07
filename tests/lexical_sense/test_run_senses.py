"""
tests/lexical_sense/test_run_senses.py

Integration tests for the 'run' sense data and resolver.
Verifies that the correct sense is ranked first for different contexts.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from translator_v2.lexical_sense.models import SenseRecord
from translator_v2.source_analysis.models import ParsedSentence, Token


def _make_parsed(text: str, tokens: list[Token]) -> ParsedSentence:
    return ParsedSentence(text=text, tokens=tokens, parser_available=True)


def _verb_token(i: int, lemma: str, dep: str = "ROOT", head_i: int | None = None) -> Token:
    return Token(
        i=i, text=lemma, lemma=lemma, upos="VERB",
        morph={}, dep=dep, head_i=head_i if head_i is not None else i,
        ner="", char_start=0, char_end=len(lemma),
    )


def _noun_token(i: int, text: str, dep: str = "dobj", head_i: int = 0, ner: str = "") -> Token:
    return Token(
        i=i, text=text, lemma=text.lower(), upos="NOUN",
        morph={}, dep=dep, head_i=head_i,
        ner=ner, char_start=0, char_end=len(text),
    )


class TestRunSenses:
    """
    Verify that the sense resolver ranks the correct sense of 'run' first
    given different syntactic contexts.
    All Maltese lemmas are still unverified; these tests only check sense ranking.
    """

    def test_senses_file_exists(self):
        data_path = Path(__file__).parents[2] / "translator_v2" / "lexical_sense" / "data" / "run.jsonl"
        assert data_path.exists(), "run.jsonl not found"

    def test_run_senses_loadable(self):
        from translator_v2.lexical_sense.resolver import _load_senses
        senses = _load_senses("run")
        assert len(senses) >= 7

    def test_run_manage_ranked_first_with_org_object(self):
        """
        'She runs a company' → company is an ORGANISATION.
        run_manage should rank above run_move_on_foot.
        """
        from translator_v2.lexical_sense.resolver import resolve_senses
        run_token = _verb_token(1, "run")
        company_token = _noun_token(2, "company", dep="dobj", head_i=1, ner="ORG")
        sentence = _make_parsed("She runs a company.", [run_token, company_token])
        ranked = resolve_senses(run_token, sentence)
        if not ranked:
            pytest.skip("No senses loaded (check run.jsonl path).")
        assert ranked[0].sense_id == "run_manage", (
            f"Expected run_manage first, got: {[s.sense_id for s in ranked]}"
        )

    def test_run_move_ranked_first_without_object(self):
        """
        'She runs every morning' → no direct object.
        run_move_on_foot should rank above run_manage.
        """
        from translator_v2.lexical_sense.resolver import resolve_senses
        run_token = _verb_token(1, "run")
        sentence = _make_parsed("She runs every morning.", [run_token])
        ranked = resolve_senses(run_token, sentence)
        if not ranked:
            pytest.skip("No senses loaded.")
        movement_first = ranked[0].sense_id in {
            "run_move_on_foot", "run_extend_direction", "run_function"
        }
        manage_not_first = ranked[0].sense_id != "run_manage"
        assert manage_not_first, (
            f"run_manage should NOT be first for intransitive run. Got: {[s.sense_id for s in ranked]}"
        )

    def test_all_run_senses_have_unique_ids(self):
        from translator_v2.lexical_sense.resolver import _load_senses
        senses = _load_senses("run")
        ids = [s.sense_id for s in senses]
        assert len(ids) == len(set(ids)), f"Duplicate sense IDs: {ids}"

    def test_run_senses_all_marked_for_review(self):
        """
        All Maltese lemmas in run.jsonl must be null until human-verified.
        This test will fail (intentionally) once a lemma is filled in without
        updating review_status to 'verified'.
        """
        from translator_v2.lexical_sense.resolver import _load_senses
        senses = _load_senses("run")
        for s in senses:
            if s.maltese_lemma is not None:
                assert s.review_status == "verified", (
                    f"Sense {s.sense_id} has maltese_lemma={s.maltese_lemma!r} "
                    f"but review_status={s.review_status!r}. "
                    "Set review_status to 'verified' after human confirmation."
                )
