"""
legacy/translator_v1.py

Re-exports the legacy MalteseTranslator under the `legacy` namespace.
The underlying code in Essentials/translator.py is NOT modified.
This module exists purely so the legacy engine can be imported and run
independently of the v2 pipeline.
"""
from __future__ import annotations

from Essentials.translator import MalteseTranslator, TranslationResult, TranslationCandidate  # noqa: F401

__all__ = ["MalteseTranslator", "TranslationResult", "TranslationCandidate"]
