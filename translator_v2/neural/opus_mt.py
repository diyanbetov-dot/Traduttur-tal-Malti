"""
translator_v2/neural/opus_mt.py

Thread-safe OPUS-MT backend for Helsinki-NLP/opus-mt-en-mt via Hugging Face Transformers.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass

from translator_v2.neural.base import NeuralBackend, NeuralCandidate

_MODEL_NAME = "Helsinki-NLP/opus-mt-en-mt"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpusStatus:
    ready: bool
    model_name: str
    load_error: str
    tokenizer_load_ms: float | None
    model_load_ms: float | None
    total_load_ms: float | None
    inference_count: int


class OpusMTBackend(NeuralBackend):
    """Hugging Face Marian MT backend for English to Maltese."""

    def __init__(
        self,
        model_name: str = _MODEL_NAME,
        cache_dir: str | None = None,
        model_dir: str | None = None,
        local_files_only: bool = False,
    ) -> None:
        self._model_name = model_name
        self._cache_dir = cache_dir or os.getenv("TRANSLATION_MODEL_CACHE_DIR") or None
        self._model_dir = model_dir or os.getenv("OPUS_MT_MODEL_DIR") or ""
        self._local_files_only = local_files_only
        self._tokenizer = None
        self._model = None
        self._load_error = ""
        self._tokenizer_load_ms: float | None = None
        self._model_load_ms: float | None = None
        self._total_load_ms: float | None = None
        self._last_inference_ms: float | None = None
        self._inference_count = 0
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return "opus_mt"

    @property
    def status(self) -> OpusStatus:
        return OpusStatus(
            ready=self._model is not None and self._tokenizer is not None,
            model_name=self._model_name,
            load_error=self._load_error,
            tokenizer_load_ms=self._tokenizer_load_ms,
            model_load_ms=self._model_load_ms,
            total_load_ms=self._total_load_ms,
            inference_count=self._inference_count,
        )

    @property
    def load_timings(self) -> dict[str, float | None]:
        return {
            "opus_tokenizer_load_ms": self._tokenizer_load_ms,
            "opus_model_load_ms": self._model_load_ms,
            "opus_total_load_ms": self._total_load_ms,
        }

    @property
    def last_inference_ms(self) -> float | None:
        return self._last_inference_ms

    @property
    def is_available(self) -> bool:
        return self.initialize(required=False).ready

    def initialize(self, *, required: bool = False) -> OpusStatus:
        if self._model is not None and self._tokenizer is not None:
            return self.status
        if self._load_error:
            if required:
                raise RuntimeError(self._load_error)
            return self.status

        with self._lock:
            if self._model is not None and self._tokenizer is not None:
                return self.status
            if self._load_error:
                if required:
                    raise RuntimeError(self._load_error)
                return self.status

            started = time.perf_counter()
            model_ref = self._model_dir or self._model_name
            try:
                from transformers import MarianMTModel, MarianTokenizer  # noqa: PLC0415

                tokenizer_started = time.perf_counter()
                self._tokenizer = MarianTokenizer.from_pretrained(
                    model_ref,
                    cache_dir=self._cache_dir,
                    local_files_only=self._local_files_only,
                )
                self._tokenizer_load_ms = (time.perf_counter() - tokenizer_started) * 1000

                model_started = time.perf_counter()
                self._model = MarianMTModel.from_pretrained(
                    model_ref,
                    cache_dir=self._cache_dir,
                    local_files_only=self._local_files_only,
                )
                self._model.eval()
                self._model_load_ms = (time.perf_counter() - model_started) * 1000
                self._total_load_ms = (time.perf_counter() - started) * 1000
            except ImportError as exc:
                self._load_error = "transformers, sentencepiece and torch are required for OPUS-MT."
                self._total_load_ms = (time.perf_counter() - started) * 1000
                if required:
                    raise RuntimeError(self._load_error) from exc
            except Exception as exc:  # noqa: BLE001
                self._load_error = f"Failed to load OPUS-MT model: {exc}"
                self._total_load_ms = (time.perf_counter() - started) * 1000
                logger.exception("Failed to load OPUS-MT")
                if required:
                    raise RuntimeError(self._load_error) from exc
        return self.status

    def translate(
        self,
        text: str,
        num_candidates: int = 1,
        beam_size: int = 5,
        max_length: int = 512,
    ) -> list[NeuralCandidate]:
        if not self.initialize(required=False).ready:
            return []

        import torch  # noqa: PLC0415

        started = time.perf_counter()
        inputs = self._tokenizer(
            [text],
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_length,
        )

        num_return = min(num_candidates, beam_size)
        with torch.inference_mode():
            outputs = self._model.generate(
                **inputs,
                num_beams=beam_size,
                num_return_sequences=num_return,
                output_scores=True,
                return_dict_in_generate=True,
                max_length=max_length,
            )

        decoded = self._tokenizer.batch_decode(outputs.sequences, skip_special_tokens=True)
        seq_scores = outputs.sequences_scores.tolist() if hasattr(outputs, "sequences_scores") else [None] * len(decoded)
        self._last_inference_ms = (time.perf_counter() - started) * 1000
        self._inference_count += 1

        return [
            NeuralCandidate(
                text=text_out.strip(),
                score=score,
                source="opus_mt",
                metadata={
                    "model": self._model_name,
                    "inference_ms": self._last_inference_ms,
                },
            )
            for text_out, score in zip(decoded, seq_scores)
        ]
