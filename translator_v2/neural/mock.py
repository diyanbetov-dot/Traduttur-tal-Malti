"""
translator_v2/neural/mock.py

Mock neural backend for use in unit tests.
Returns fixed or echo candidates without downloading any model.
"""
from __future__ import annotations

from translator_v2.neural.base import NeuralBackend, NeuralCandidate


class MockBackend(NeuralBackend):
    """
    Always available backend that returns canned responses.
    Used in tests and CI where model download is not allowed.
    """

    def __init__(self, fixed_response: str | None = None) -> None:
        """
        Args:
            fixed_response: If set, always return this Maltese string.
                            If None, return "[MOCK: {source}]".
        """
        self._fixed_response = fixed_response

    @property
    def name(self) -> str:
        return "mock"

    @property
    def is_available(self) -> bool:
        return True

    def translate(
        self,
        text: str,
        num_candidates: int = 1,
        beam_size: int = 5,
        max_length: int = 512,
    ) -> list[NeuralCandidate]:
        base = self._fixed_response if self._fixed_response else f"[MOCK: {text}]"
        candidates: list[NeuralCandidate] = []
        for i in range(num_candidates):
            suffix = f" (beam {i})" if i > 0 else ""
            candidates.append(NeuralCandidate(
                text=base + suffix,
                score=float(-0.1 * (i + 1)),
                source="mock",
                metadata={"beam": i},
            ))
        return candidates
