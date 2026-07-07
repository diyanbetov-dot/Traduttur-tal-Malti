"""
translator_v2/source_analysis/base.py

Abstract interface for English parsers.
Implementations must be in separate files (e.g., english_parser.py).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from translator_v2.source_analysis.models import ParsedSentence


class EnglishParser(ABC):
    """Abstract base for English dependency parsers."""

    @abstractmethod
    def parse(self, text: str) -> ParsedSentence:
        """Parse English text and return a structured sentence."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the underlying parser is installed and loaded."""
        ...
