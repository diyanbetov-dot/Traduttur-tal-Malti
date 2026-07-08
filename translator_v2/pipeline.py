"""
translator_v2/pipeline.py

The v2 hybrid translation pipeline: spaCy analysis -> OPUS-MT candidates ->
rule/lexicon validation and corrections -> final ranked translation.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from translator_v2.configuration import V2Config
from translator_v2.lexical_sense.models import SenseRecord
from translator_v2.lexical_sense.resolver import resolve_senses
from translator_v2.neural.base import NeuralCandidate
from translator_v2.neural.registry import get_backend
from translator_v2.result import TranslationCandidate, TranslationResult, TranslationWarning
from translator_v2.source_analysis.english_parser import get_parser
from translator_v2.source_analysis.models import ParsedSentence

logger = logging.getLogger(__name__)


@dataclass
class TranslationConstraints:
    selected_sense: SenseRecord | None = None
    subject_features: list[str] = field(default_factory=list)
    object_semantic_class: str | None = None
    preferred_maltese_lemmas: list[str] = field(default_factory=list)
    forbidden_senses: list[str] = field(default_factory=list)
    preserve_entities: list[str] = field(default_factory=list)
    preserve_numbers: list[str] = field(default_factory=list)
    required_terms: list[str] = field(default_factory=list)
    domain: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_sense": self.selected_sense.sense_id if self.selected_sense else None,
            "subject_features": self.subject_features,
            "object_semantic_class": self.object_semantic_class,
            "preferred_maltese_lemmas": self.preferred_maltese_lemmas,
            "forbidden_senses": self.forbidden_senses,
            "preserve_entities": self.preserve_entities,
            "preserve_numbers": self.preserve_numbers,
            "required_terms": self.required_terms,
            "domain": self.domain,
        }


class TranslationPipeline:
    """Runs the full v2 translation pipeline."""

    def __init__(self, config: V2Config) -> None:
        self._config = config
        self._parser = get_parser(config.spacy_model)
        self._backend = get_backend(
            config.backend,
            cache_dir=config.model_cache_dir or None,
            model_dir=config.opus_model_dir or None,
            model_name=config.opus_model_name,
            local_files_only=config.local_files_only,
        )
        self._initialize_lock = threading.Lock()
        self._initialized = False
        self._initialization_error = ""
        self._initialization_timings: dict[str, float | bool | str | None] = {}

    @property
    def backend_name(self) -> str:
        return self._backend.name

    def initialize(self) -> dict[str, float | bool | str | None]:
        """Load required resources once for the selected backend."""
        if self._initialized:
            return dict(self._initialization_timings)
        if self._initialization_error:
            raise RuntimeError(self._initialization_error)

        with self._initialize_lock:
            if self._initialized:
                return dict(self._initialization_timings)
            started = time.perf_counter()
            timings: dict[str, float | bool | str | None] = {
                "backend_mode": self._config.backend,
                "rule_postprocessing_enabled": self._config.rule_postprocessing_enabled,
            }
            try:
                if self._config.preload_spacy:
                    parser_started = time.perf_counter()
                    parser_status = self._parser.initialize(required=True)
                    timings["spacy_load_ms"] = parser_status.load_ms
                    timings["spacy_ready"] = parser_status.ready
                    timings["spacy_initialize_call_ms"] = round((time.perf_counter() - parser_started) * 1000, 2)

                if self._config.requires_opus and self._config.preload_opus:
                    opus_started = time.perf_counter()
                    opus_status = self._backend.initialize(required=True)
                    timings["opus_ready"] = opus_status.ready
                    timings["opus_initialize_call_ms"] = round((time.perf_counter() - opus_started) * 1000, 2)
                    for key, value in getattr(self._backend, "load_timings", {}).items():
                        timings[key] = value

                if self._config.uses_rules:
                    rules_started = time.perf_counter()
                    from translator_v2.maltese.lexicon.database import get_lexicon_db  # noqa: PLC0415
                    get_lexicon_db()
                    from translator_v2.maltese.lexicon import terminology  # noqa: F401, PLC0415
                    from translator_v2.maltese.validation import agreement  # noqa: F401, PLC0415
                    from translator_v2.candidates import corrections  # noqa: F401, PLC0415
                    timings["rule_resources_load_ms"] = round((time.perf_counter() - rules_started) * 1000, 2)

                timings["total_initialize_ms"] = round((time.perf_counter() - started) * 1000, 2)
                self._initialization_timings = timings
                self._initialized = True
                logger.warning("translator_v2 initialized: %s", timings)
                return dict(timings)
            except Exception as exc:  # noqa: BLE001
                self._initialization_error = str(exc)
                logger.exception("translator_v2 initialization failed")
                raise

    def ready_status(self) -> dict[str, Any]:
        parser_status = self._parser.status
        backend_status = getattr(self._backend, "status", None)
        opus_ready = True
        opus_error = ""
        if self._config.requires_opus:
            opus_ready = bool(getattr(backend_status, "ready", False))
            opus_error = str(getattr(backend_status, "load_error", ""))
        spacy_ready = (not self._config.preload_spacy) or parser_status.ready
        ready = self._initialized and not self._initialization_error and spacy_ready and opus_ready
        return {
            "ok": ready,
            "status": "ready" if ready else "not_ready",
            "engine": "v2",
            "backend": self._config.backend,
            "spacy_ready": spacy_ready,
            "opus_ready": opus_ready,
            "core_resources_ready": self._initialized and not self._initialization_error,
            "initialization_error": self._initialization_error,
            "opus_error": opus_error,
            "timings_ms": dict(self._initialization_timings),
        }

    def _parse(self, text: str) -> ParsedSentence:
        return self._parser.parse(text)

    def _analyse_senses(self, sentence: ParsedSentence) -> dict[int, list[SenseRecord]]:
        result: dict[int, list[SenseRecord]] = {}
        for token in sentence.tokens:
            if token.upos in {"VERB", "NOUN"} and len(token.lemma) > 2:
                senses = resolve_senses(token, sentence)
                if senses:
                    result[token.i] = senses
        return result

    def _build_constraints(self, sentence: ParsedSentence, senses: dict[int, list[SenseRecord]]) -> TranslationConstraints:
        constraints = TranslationConstraints()
        constraints.preserve_entities = [e.text for e in sentence.entities if e.label not in {"DATE", "TIME", "CARDINAL", "ORDINAL", "QUANTITY", "MONEY", "PERCENT"}]
        constraints.preserve_numbers = [
            t.text for t in sentence.tokens
            if t.upos in {"NUM"} or t.morph.get("NumType") in {"Card", "Ord"}
        ]
        root = sentence.root_token
        if root and root.i in senses:
            constraints.selected_sense = senses[root.i][0]
        return constraints

    def _generate_candidates(self, text: str) -> list[NeuralCandidate]:
        if self._config.backend == "rules":
            return []
        if not self._backend.is_available:
            return []
        return self._backend.translate(
            text,
            num_candidates=self._config.num_candidates,
            beam_size=self._config.beam_size,
            max_length=self._config.max_input_length,
        )

    def _validate_candidate(
        self,
        candidate: NeuralCandidate,
        source_text: str,
        constraints: TranslationConstraints,
        sentence: ParsedSentence,
    ) -> list[TranslationWarning]:
        warnings: list[TranslationWarning] = []
        text = candidate.text
        if not text.strip():
            warnings.append(TranslationWarning("OTHER", "Empty translation output.", "error"))
            return warnings

        if text.strip().lower() == source_text.strip().lower() and len(source_text.split()) > 1:
            warnings.append(TranslationWarning(
                "UNTRANSLATED_TOKEN", "Output is identical to English source.", "error"
            ))

        if self._config.uses_rules:
            from translator_v2.maltese.validation.agreement import (  # noqa: PLC0415
                validate_coordination_agreement,
                validate_subject_verb_agreement,
                validate_tense_aspect_agreement,
            )
            warnings.extend(validate_coordination_agreement(text, sentence))
            warnings.extend(validate_subject_verb_agreement(text, sentence))
            warnings.extend(validate_tense_aspect_agreement(text, sentence))


        source_words = {w.lower() for w in source_text.split() if len(w) > 3}
        output_words = {w.lower().rstrip(".,?!") for w in text.split()}
        untranslated = source_words & output_words
        from translator_v2.maltese.lexicon.terminology import PREFERRED_TERMS  # noqa: PLC0415
        untranslated = {
            w for w in untranslated
            if w not in {"that", "this", "they", "have", "does"} and w not in PREFERRED_TERMS
        }
        for w in sorted(untranslated):
            warnings.append(TranslationWarning(
                "UNTRANSLATED_TOKEN",
                f"Possibly untranslated English word: '{w}'",
                "warning",
                suggestions=[f"Check Maltese equivalent of '{w}'"],
            ))

        for entity in constraints.preserve_entities:
            if entity not in text:
                warnings.append(TranslationWarning(
                    "NAMED_ENTITY_ERROR", f"Named entity '{entity}' not found in output.", "warning"
                ))
        for number in constraints.preserve_numbers:
            if number not in text:
                warnings.append(TranslationWarning(
                    "NUMBER_PRESERVATION", f"Number '{number}' not found in output.", "warning"
                ))
        return warnings

    def _rerank(self, candidates: list[TranslationCandidate], constraints: TranslationConstraints) -> list[TranslationCandidate]:
        def key(c: TranslationCandidate):
            errors = sum(1 for w in c.validation_warnings if w.severity == "error")
            warnings_count = sum(1 for w in c.validation_warnings if w.severity == "warning")
            score = -(c.model_score or 0.0)
            return (errors, warnings_count, score)

        sorted_candidates = sorted(candidates, key=key)
        for rank, c in enumerate(sorted_candidates):
            reasons: list[str] = []
            if c.error_count == 0:
                reasons.append("no validation errors")
            if c.warning_count == 0:
                reasons.append("no validation warnings")
            if c.model_score is not None:
                reasons.append(f"model score {c.model_score:.3f}")
            if rank == 0:
                reasons.insert(0, "selected as best candidate")
            c.ranking_reasons.clear()
            c.ranking_reasons.extend(reasons)
        return sorted_candidates

    def run(self, text: str) -> TranslationResult:
        t_start = time.perf_counter()
        timings: dict[str, float] = {}
        pipeline_warnings: list[TranslationWarning] = []

        if not self._initialized:
            self.initialize()

        step = time.perf_counter()
        sentence = self._parse(text)
        timings["spacy_parse_ms"] = round((time.perf_counter() - step) * 1000, 2)
        if not sentence.parser_available:
            for msg in sentence.warnings:
                pipeline_warnings.append(TranslationWarning("PARSER_UNAVAILABLE", msg, "warning"))

        step = time.perf_counter()
        senses = self._analyse_senses(sentence)
        timings["sense_ms"] = round((time.perf_counter() - step) * 1000, 2)

        step = time.perf_counter()
        constraints = self._build_constraints(sentence, senses)
        timings["constraints_ms"] = round((time.perf_counter() - step) * 1000, 2)

        step = time.perf_counter()
        neural_candidates = self._generate_candidates(text)
        timings["opus_inference_ms"] = round((time.perf_counter() - step) * 1000, 2)
        opus_translation = neural_candidates[0].text if neural_candidates else ""
        if not neural_candidates:
            pipeline_warnings.append(TranslationWarning(
                "BACKEND_UNAVAILABLE",
                f"Backend '{self._config.backend}' returned no candidates.",
                "error" if self._config.requires_opus else "warning",
            ))

        step = time.perf_counter()
        translation_candidates: list[TranslationCandidate] = []
        for nc in neural_candidates:
            warnings = self._validate_candidate(nc, text, constraints, sentence)
            tc = TranslationCandidate(
                text=nc.text,
                source=nc.source,
                model_score=nc.score,
                validation_warnings=warnings,
                applied_constraints=[
                    f"preserve_entities={constraints.preserve_entities}",
                    f"preserve_numbers={constraints.preserve_numbers}",
                ] if constraints.preserve_entities or constraints.preserve_numbers else [],
            )
            translation_candidates.append(tc)

            if self._config.uses_rules:
                from translator_v2.candidates.corrections import apply_candidate_corrections  # noqa: PLC0415
                corrected_variants = apply_candidate_corrections(tc, sentence)
                for cv in corrected_variants:
                    from translator_v2.neural.base import NeuralCandidate  # noqa: PLC0415
                    nc_variant = NeuralCandidate(text=cv.text, score=cv.model_score, source=cv.source)
                    cv.validation_warnings = self._validate_candidate(nc_variant, text, constraints, sentence)
                    translation_candidates.append(cv)
        timings["rule_validation_ms"] = round((time.perf_counter() - step) * 1000, 2)

        step = time.perf_counter()
        ranked = self._rerank(translation_candidates, constraints)
        timings["rerank_ms"] = round((time.perf_counter() - step) * 1000, 2)

        best_candidate = ranked[0] if ranked else None
        selected_rule_changes = list(best_candidate.corrections) if best_candidate else []
        best_text = best_candidate.text if best_candidate else ""
        final_text = self._post_process_clean(best_text, text)
        latency = (time.perf_counter() - t_start) * 1000
        timings["total_ms"] = round(latency, 2)

        logger.warning(
            "translator_v2 request backend=%s chars=%s timings=%s rules_changed=%s",
            self._config.backend,
            len(text),
            timings,
            bool(selected_rule_changes),
        )

        return TranslationResult(
            source_text=text,
            translated_text=final_text,
            engine="v2",
            backend=self._config.backend,
            alternatives=ranked,
            warnings=pipeline_warnings,
            metadata={
                "direction": "en-mt",
                "backend_mode": self._config.backend,
                "neural_backend": self._backend.name,
                "opus_translation": opus_translation,
                "rule_changes": selected_rule_changes,
                "selected_sense": constraints.selected_sense.sense_id if constraints.selected_sense else None,
                "constraints": constraints.to_dict(),
                "parser_available": sentence.parser_available,
                "num_senses_found": sum(len(v) for v in senses.values()),
                "timings_ms": timings,
            },
            latency_ms=latency,
        )

    def _post_process_clean(self, text: str, source: str) -> str:
        if not text:
            return ""

        import re  # noqa: PLC0415
        cleaned = text.strip()
        cleaned = re.sub(r"\s*-\s*", "-", cleaned)
        cleaned = re.sub(r"\s*'\s*", "'", cleaned)
        cleaned = re.sub(r"(\w+')(\w+)", r"\1 \2", cleaned)
        cleaned = re.sub(r"(\b[fltmbn])'\s+", r"\1'", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        if cleaned and (source[0].isupper() or source.strip().endswith((".", "?", "!")) or len(source.split()) > 1):
            cleaned = cleaned[0].upper() + cleaned[1:]
        cleaned = re.sub(r"\s+([.,?!;:])", r"\1", cleaned)
        if self._config.uses_rules:
            from translator_v2.maltese.lexicon.terminology import apply_terminology_overrides  # noqa: PLC0415
            cleaned = apply_terminology_overrides(cleaned)
        return cleaned
