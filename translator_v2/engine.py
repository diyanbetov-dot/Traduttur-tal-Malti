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

        result = self._get_pipeline().run(text)
        result.metadata["direction"] = direction
        return result

    @property
    def en_to_mt(self) -> dict:
        return {}

    @property
    def mt_to_en(self) -> dict:
        return {}
