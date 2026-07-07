"""
translator_v2/configuration.py

Environment-variable-driven configuration for the v2 engine.
All settings have safe defaults; no setting is required.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool_env(key: str, default: bool = False) -> bool:
    return os.getenv(key, "").strip().casefold() in {"1", "true", "yes", "on"} or (
        default and os.getenv(key, "").strip() == ""
    )


def _int_env(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class V2Config:
    # Engine selection
    engine: str = "v2"            # "legacy" | "v2"
    backend: str = "mock"         # "mock" | "opus_mt" | "nllb"

    # Neural translation
    num_candidates: int = 5
    beam_size: int = 5
    max_input_length: int = 512
    model_cache_dir: str = ""     # empty = Hugging Face default cache

    # spaCy
    spacy_model: str = "en_core_web_sm"

    # Register
    register: str = "conversational"   # "conversational" | "formal"

    # Validation
    enable_morphology_validation: bool = True
    enable_preservation_checks: bool = True
    enable_sense_validation: bool = True

    @classmethod
    def from_env(cls) -> "V2Config":
        return cls(
            engine=os.getenv("TRANSLATOR_ENGINE", "v2"),
            backend=os.getenv("TRANSLATION_BACKEND", "mock"),
            num_candidates=_int_env("TRANSLATION_NUM_CANDIDATES", 5),
            beam_size=_int_env("TRANSLATION_BEAM_SIZE", 5),
            max_input_length=_int_env("TRANSLATION_MAX_INPUT_LENGTH", 512),
            model_cache_dir=os.getenv("TRANSLATION_MODEL_CACHE_DIR", ""),
            spacy_model=os.getenv("SPACY_MODEL", "en_core_web_sm"),
            register=os.getenv("TRANSLATION_REGISTER", "conversational"),
            enable_morphology_validation=_bool_env("ENABLE_MORPHOLOGY_VALIDATION", True),
            enable_preservation_checks=_bool_env("ENABLE_PRESERVATION_CHECKS", True),
            enable_sense_validation=_bool_env("ENABLE_SENSE_VALIDATION", True),
        )
