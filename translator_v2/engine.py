"""
translator_v2/engine.py

V2Engine: public entry point for the hybrid translator.
"""
from __future__ import annotations

import threading
from typing import Any

from translator_v2.configuration import V2Config
from translator_v2.pipeline import TranslationPipeline
from translator_v2.result import TranslationResult, TranslationWarning


class V2Engine:
    """Top-level engine used by Flask when TRANSLATOR_ENGINE=v2."""

    def __init__(self, config: V2Config | None = None) -> None:
        self._config = config or V2Config.from_env()
        self._pipeline: TranslationPipeline | None = None
        self._pipeline_lock = threading.Lock()

    @property
    def config(self) -> V2Config:
        return self._config

    def _get_pipeline(self) -> TranslationPipeline:
        if self._pipeline is not None:
            return self._pipeline
        with self._pipeline_lock:
            if self._pipeline is None:
                self._pipeline = TranslationPipeline(self._config)
            return self._pipeline

    def initialize(self) -> dict[str, float | bool | str | None]:
        return self._get_pipeline().initialize()

    def ready_status(self) -> dict[str, Any]:
        if self._pipeline is None:
            return {
                "ok": False,
                "status": "not_ready",
                "engine": "v2",
                "backend": self._config.backend,
                "spacy_ready": False,
                "opus_ready": False if self._config.requires_opus else True,
                "core_resources_ready": False,
                "initialization_error": "translator has not been initialized",
            }
        return self._pipeline.ready_status()

    def supports_direction(self, direction: str) -> bool:
        return direction == "en-mt"

    def translate(self, text: str, direction: str = "en-mt") -> TranslationResult:
        if not text or not text.strip():
            return TranslationResult(
                source_text=text,
                translated_text="",
                engine="v2",
                backend=self._config.backend,
                warnings=[TranslationWarning("OTHER", "Empty input.", "error")],
                metadata={"direction": direction},
            )

        if direction == "mt-en":
            return TranslationResult(
                source_text=text,
                translated_text="",
                engine="v2",
                backend=self._config.backend,
                warnings=[TranslationWarning(
                    "OTHER",
                    "mt-en direction is not implemented in v2 yet.",
                    "error",
                )],
                metadata={"direction": direction, "unsupported": True},
            )

        # Split multi-sentence input into individual sentences so each is
        # translated independently. This prevents the neural model from
        # getting confused by multiple sentences and stops rule-based
        # corrections (verb-person, idioms, etc.) from bleeding across
        # sentence boundaries.
        sentences = self._split_sentences(text)
        if len(sentences) <= 1:
            result = self._get_pipeline().run(text)
            result.metadata["direction"] = direction
            return result

        # Translate each sentence individually and combine results.
        translated_parts: list[str] = []
        all_warnings: list[TranslationWarning] = []
        combined_metadata: dict = {}
        for sent in sentences:
            r = self._get_pipeline().run(sent)
            translated_parts.append(r.translated_text)
            all_warnings.extend(r.warnings)
            combined_metadata = r.metadata  # keep last sentence's metadata as representative

        combined_text = " ".join(translated_parts)
        combined_metadata["direction"] = direction
        combined_metadata["multi_sentence"] = True
        combined_metadata["sentence_count"] = len(sentences)

        return TranslationResult(
            source_text=text,
            translated_text=combined_text,
            engine="v2",
            backend=self._config.backend,
            warnings=all_warnings,
            metadata=combined_metadata,
        )

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Split text into individual sentences on sentence-final punctuation."""
        import re  # noqa: PLC0415
        # Split on ., !, ? followed by whitespace (or end of string),
        # but keep the punctuation attached to the preceding sentence.
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return [p.strip() for p in parts if p.strip()]

    @property
    def en_to_mt(self) -> dict:
        return {}

    @property
    def mt_to_en(self) -> dict:
        return {}
