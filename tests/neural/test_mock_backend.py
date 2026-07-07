"""
tests/neural/test_mock_backend.py

Unit tests for the mock neural backend.
No model download required.
"""
from __future__ import annotations

import pytest
from translator_v2.neural.mock import MockBackend
from translator_v2.neural.registry import get_backend


class TestMockBackend:
    def test_is_available(self):
        backend = MockBackend()
        assert backend.is_available is True

    def test_name(self):
        backend = MockBackend()
        assert backend.name == "mock"

    def test_returns_one_candidate_by_default(self):
        backend = MockBackend()
        results = backend.translate("She runs a company.", num_candidates=1)
        assert len(results) == 1

    def test_returns_multiple_candidates(self):
        backend = MockBackend()
        results = backend.translate("She runs a company.", num_candidates=3)
        assert len(results) == 3

    def test_fixed_response(self):
        backend = MockBackend(fixed_response="Tmexxi kumpanija.")
        results = backend.translate("She runs a company.", num_candidates=1)
        assert results[0].text == "Tmexxi kumpanija."

    def test_echo_response_contains_source(self):
        backend = MockBackend()
        results = backend.translate("Hello world", num_candidates=1)
        assert "Hello world" in results[0].text

    def test_scores_are_negative(self):
        backend = MockBackend()
        results = backend.translate("test", num_candidates=2)
        for r in results:
            assert r.score is not None
            assert r.score < 0

    def test_registry_returns_mock(self):
        backend = get_backend("mock")
        assert backend.name == "mock"
        assert backend.is_available is True

    def test_registry_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown neural backend"):
            get_backend("nonexistent_backend_xyz")
