"""
translator_v2/engine.py

V2Engine: the main entry point for the v2 translation system.
Used by the Flask app when TRANSLATOR_ENGINE=v2.
"""
from __future__ import annotations

from pathlib import Path

from translator_v2.configuration import V2Config
from translator_v2.pipeline import TranslationPipeline
from translator_v2.result import TranslationResult, TranslationWarning


class V2Engine:
    """
    Top-level engine that coordinates configuration and the pipeline.
    Provides the same interface as the legacy MalteseTranslator for
    Flask compatibility: translate(text, direction) -> TranslationResult.
    """

    def __init__(self, config: V2Config | None = None) -> None:
        self._config = config or V2Config.from_env()
        self._pipeline: TranslationPipeline | None = None

    def _get_pipeline(self) -> TranslationPipeline:
        if self._pipeline is None:
            self._pipeline = TranslationPipeline(self._config)
        return self._pipeline

    def translate(self, text: str, direction: str = "en-mt") -> TranslationResult:
        if not text or not text.strip():
            return TranslationResult(
                source_text=text,
                translated_text="",
                engine="v2",
                warnings=[TranslationWarning("OTHER", "Empty input.", "error")],
                metadata={"direction": direction},
            )

        if direction == "mt-en":
            return TranslationResult(
                source_text=text,
                translated_text=text,
                engine="v2",
                warnings=[TranslationWarning(
                    "OTHER",
                    "mt-en direction not yet implemented in v2. Use legacy engine.",
                    "warning",
                )],
                metadata={"direction": direction},
            )

        result = self._get_pipeline().run(text)
        result.metadata["direction"] = direction
        return result

    # Compatibility properties for Flask health endpoint
    @property
    def en_to_mt(self) -> dict:
        return {}

    @property
    def mt_to_en(self) -> dict:
        return {}
