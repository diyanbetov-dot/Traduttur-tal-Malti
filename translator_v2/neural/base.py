"""
translator_v2/neural/base.py

Abstract interface for neural translation backends.
All backends must implement this interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class NeuralCandidate:
    """A single candidate from a neural translation backend."""
    text: str
    score: float | None = None    # Log-probability or beam score; None if not available
    source: str = "neural"
    metadata: dict = field(default_factory=dict)


class NeuralBackend(ABC):
    """Abstract base for neural translation backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique backend identifier."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the backend is ready to translate."""
        ...

    @abstractmethod
    def translate(
        self,
        text: str,
        num_candidates: int = 1,
        beam_size: int = 5,
        max_length: int = 512,
    ) -> list[NeuralCandidate]:
        """
        Translate English text and return up to num_candidates Maltese candidates.
        If the backend is unavailable, return an empty list — do not raise.
        """
        ...
