"""
translator_v2/neural/opus_mt.py

Backend adapter for Helsinki-NLP/opus-mt-en-mt via Hugging Face Transformers.

Model: Helsinki-NLP/opus-mt-en-mt
Licence: CC-BY 4.0

IMPORTANT:
- Model is NOT downloaded at import time.
- First call to translate() triggers download (~300 MB).
- Model weights must NOT be committed to Git.
- Add the cache directory to .gitignore.

Install:
    pip install transformers sentencepiece torch

Environment:
    TRANSLATION_MODEL_CACHE_DIR  — optional custom Hugging Face cache directory
"""
from __future__ import annotations

import logging
import os

from translator_v2.neural.base import NeuralBackend, NeuralCandidate

_MODEL_NAME = "Helsinki-NLP/opus-mt-en-mt"


class OpusMTBackend(NeuralBackend):
    """Hugging Face Marian MT backend for English → Maltese."""

    def __init__(self, model_name: str = _MODEL_NAME, cache_dir: str | None = None) -> None:
        self._model_name = model_name
        self._cache_dir = cache_dir or os.getenv("TRANSLATION_MODEL_CACHE_DIR") or None
        self._tokenizer = None
        self._model = None
        self._load_error: str = ""

    def _ensure_loaded(self) -> bool:
        if self._model is not None:
            return True
        if self._load_error:
            return False
        try:
            from transformers import MarianMTModel, MarianTokenizer  # noqa: PLC0415
            self._tokenizer = MarianTokenizer.from_pretrained(
                self._model_name, cache_dir=self._cache_dir
            )
            self._model = MarianMTModel.from_pretrained(
                self._model_name, cache_dir=self._cache_dir
            )
            self._model.eval()
            return True
        except ImportError:
            self._load_error = (
                "transformers and sentencepiece are not installed. "
                "Install with: pip install transformers sentencepiece torch"
            )
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).error(f"Failed to load {self._model_name}: {exc}")
        return False

    @property
    def name(self) -> str:
        return "opus_mt"

    @property
    def is_available(self) -> bool:
        return self._ensure_loaded()

    def translate(
        self,
        text: str,
        num_candidates: int = 1,
        beam_size: int = 5,
        max_length: int = 512,
    ) -> list[NeuralCandidate]:
        if not self._ensure_loaded():
            return []

        import torch  # noqa: PLC0415

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

        sequences = outputs.sequences  # shape: (num_return, seq_len)
        decoded = self._tokenizer.batch_decode(sequences, skip_special_tokens=True)

        # Sequence scores: sum of log probs
        seq_scores = outputs.sequences_scores.tolist() if hasattr(outputs, "sequences_scores") else [None] * len(decoded)

        candidates: list[NeuralCandidate] = []
        for text_out, score in zip(decoded, seq_scores):
            candidates.append(NeuralCandidate(
                text=text_out.strip(),
                score=score,
                source="opus_mt",
                metadata={"model": self._model_name},
            ))
        return candidates
