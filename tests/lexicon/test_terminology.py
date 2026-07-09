"""
tests/lexicon/test_terminology.py

Unit tests for terminology preferred override mappings.
"""
from __future__ import annotations

from translator_v2.maltese.lexicon.terminology import apply_terminology_overrides


class TestTerminology:
    def test_replaces_downstairs_and_upstairs(self):
        assert apply_terminology_overrides("went downstairs") == "went isfel"
        assert apply_terminology_overrides("went upstairs") == "went fuq"

    def test_replaces_case_insensitively_and_preserves_capitalization(self):
        assert apply_terminology_overrides("Downstairs") == "Isfel"
        assert apply_terminology_overrides("DOWNSTAIRS") == "ISFEL"
        assert apply_terminology_overrides("downstairs") == "isfel"

    def test_normalizes_bad_yesterday_surface_to_dictionary_base(self):
        assert apply_terminology_overrides("Bieraħ mort.") == "Lbieraħ mort."
        assert apply_terminology_overrides("bieraħ mort.") == "lbieraħ mort."

    def test_does_not_replace_within_other_words(self):
        # "downstairsy" should not be touched
        assert apply_terminology_overrides("downstairsy") == "downstairsy"