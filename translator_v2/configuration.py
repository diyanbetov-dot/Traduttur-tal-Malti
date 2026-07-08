"""
translator_v2/configuration.py

Validated runtime configuration for the v2 hybrid translator.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationError(ValueError):
    """Raised when the translator runtime configuration is invalid."""


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
VALID_ENGINES = {"legacy", "v2"}
VALID_BACKENDS = {"hybrid", "opus_mt", "rules", "mock"}


def _bool_env(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return default
    normalized = value.strip().casefold()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ConfigurationError(f"{key} must be one of: 1,true,yes,on,0,false,no,off")


def _int_env(key: str, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    raw = os.getenv(key, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{key} must be an integer, got {raw!r}") from exc
    if minimum is not None and value < minimum:
        raise ConfigurationError(f"{key} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ConfigurationError(f"{key} must be <= {maximum}")
    return value


def _choice_env(key: str, default: str, valid: set[str]) -> str:
    value = os.getenv(key, default).strip().casefold()
    if value not in valid:
        choices = ", ".join(sorted(valid))
        raise ConfigurationError(f"{key} must be one of: {choices}. Got {value!r}.")
    return value


@dataclass(frozen=True)
class V2Config:
    # Engine selection
    engine: str = "v2"
    backend: str = "hybrid"

    # Startup/resource policy
    preload_spacy: bool = True
    preload_opus: bool = True
    rule_postprocessing_enabled: bool = True
    local_files_only: bool = False

    # Neural translation. Keep quality defaults: do not weaken OPUS output for speed.
    num_candidates: int = 5
    beam_size: int = 5
    max_input_length: int = 512
    model_cache_dir: str = ""
    opus_model_name: str = "Helsinki-NLP/opus-mt-en-mt"
    opus_model_dir: str = ""

    # spaCy
    spacy_model: str = "en_core_web_sm"

    # Register
    register: str = "conversational"

    # Validation
    enable_morphology_validation: bool = True
    enable_preservation_checks: bool = True
    enable_sense_validation: bool = True

    @property
    def requires_opus(self) -> bool:
        return self.backend in {"hybrid", "opus_mt"}

    @property
    def uses_rules(self) -> bool:
        return self.backend in {"hybrid", "rules"} and self.rule_postprocessing_enabled

    @classmethod
    def from_env(cls) -> "V2Config":
        offline_default = _bool_env("TRANSFORMERS_OFFLINE", False) or _bool_env("HF_HUB_OFFLINE", False)
        return cls(
            engine=_choice_env("TRANSLATOR_ENGINE", "v2", VALID_ENGINES),
            backend=_choice_env("TRANSLATION_BACKEND", "hybrid", VALID_BACKENDS),
            preload_spacy=_bool_env("PRELOAD_SPACY", True),
            preload_opus=_bool_env("PRELOAD_OPUS", True),
            rule_postprocessing_enabled=_bool_env("RULE_POSTPROCESSING_ENABLED", True),
            local_files_only=_bool_env("TRANSLATION_LOCAL_FILES_ONLY", offline_default),
            num_candidates=_int_env("TRANSLATION_NUM_CANDIDATES", 5, minimum=1, maximum=8),
            beam_size=_int_env("TRANSLATION_BEAM_SIZE", 5, minimum=1, maximum=8),
            max_input_length=_int_env("TRANSLATION_MAX_INPUT_LENGTH", 512, minimum=32, maximum=1024),
            model_cache_dir=os.getenv("TRANSLATION_MODEL_CACHE_DIR", ""),
            opus_model_name=os.getenv("OPUS_MT_MODEL_NAME", "Helsinki-NLP/opus-mt-en-mt"),
            opus_model_dir=os.getenv("OPUS_MT_MODEL_DIR", ""),
            spacy_model=os.getenv("SPACY_MODEL", "en_core_web_sm"),
            register=os.getenv("TRANSLATION_REGISTER", "conversational"),
            enable_morphology_validation=_bool_env("ENABLE_MORPHOLOGY_VALIDATION", True),
            enable_preservation_checks=_bool_env("ENABLE_PRESERVATION_CHECKS", True),
            enable_sense_validation=_bool_env("ENABLE_SENSE_VALIDATION", True),
        )
