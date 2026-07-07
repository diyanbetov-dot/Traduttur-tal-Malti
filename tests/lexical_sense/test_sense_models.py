"""
tests/lexical_sense/test_sense_models.py

Unit tests for the SenseRecord dataclass.
"""
from __future__ import annotations

import pytest
from translator_v2.lexical_sense.models import SenseRecord


def make_sense(**kwargs) -> SenseRecord:
    defaults = dict(
        english_lemma="run",
        sense_id="run_test",
        pos="VERB",
        definition="Test sense.",
        maltese_lemma=None,
        maltese_construction=None,
    )
    defaults.update(kwargs)
    return SenseRecord(**defaults)


class TestSenseRecord:
    def test_defaults(self):
        s = make_sense()
        assert s.review_status == "needs_human_review"
        assert s.confidence_type == "machine_suggested"
        assert s.transitivity == "unknown"

    def test_invalid_review_status_reset(self):
        s = make_sense(review_status="nonsense")
        assert s.review_status == "needs_human_review"

    def test_to_dict_has_all_fields(self):
        s = make_sense(sense_id="run_manage", maltese_lemma="mexa")
        d = s.to_dict()
        assert d["sense_id"] == "run_manage"
        assert d["maltese_lemma"] == "mexa"
        assert "review_status" in d
        assert "dep_frame" in d

    def test_roundtrip(self):
        s = make_sense(
            sense_id="run_move",
            transitivity="intransitive",
            subject_semantic_classes=["ANIMATE"],
            collocations=["morning", "race"],
        )
        d = s.to_dict()
        s2 = SenseRecord.from_dict(d)
        assert s2.sense_id == s.sense_id
        assert s2.transitivity == s.transitivity
        assert s2.subject_semantic_classes == s.subject_semantic_classes
        assert s2.collocations == s.collocations
