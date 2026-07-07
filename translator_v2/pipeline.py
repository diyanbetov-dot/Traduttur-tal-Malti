"""
translator_v2/pipeline.py

The core v2 translation pipeline.
Orchestrates: parse → sense → constrain → neural → validate → correct → rerank.
"""
from __future__ import annotations

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


@dataclass
class TranslationConstraints:
    """
    Deterministic constraints derived from the English source.
    Produced before neural translation; used during validation and reranking.
    """
    selected_sense: SenseRecord | None = None
    subject_features: list[str] = field(default_factory=list)
    object_semantic_class: str | None = None
    preferred_maltese_lemmas: list[str] = field(default_factory=list)   # empty until human-verified
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
    """Runs the full v2 translation pipeline for one sentence."""

    def __init__(self, config: V2Config) -> None:
        self._config = config
        self._parser = get_parser(config.spacy_model)
        self._backend = get_backend(config.backend)

    # ------------------------------------------------------------------
    # Step 1: Parse
    # ------------------------------------------------------------------

    def _parse(self, text: str) -> ParsedSentence:
        return self._parser.parse(text)

    # ------------------------------------------------------------------
    # Step 2: Sense analysis
    # ------------------------------------------------------------------

    def _analyse_senses(self, sentence: ParsedSentence) -> dict[int, list[SenseRecord]]:
        """Return mapping of token index → ranked senses for content words."""
        result: dict[int, list[SenseRecord]] = {}
        for token in sentence.tokens:
            if token.upos in {"VERB", "NOUN"} and len(token.lemma) > 2:
                senses = resolve_senses(token, sentence)
                if senses:
                    result[token.i] = senses
        return result

    # ------------------------------------------------------------------
    # Step 3: Constraints
    # ------------------------------------------------------------------

    def _build_constraints(
        self,
        sentence: ParsedSentence,
        senses: dict[int, list[SenseRecord]],
    ) -> TranslationConstraints:
        constraints = TranslationConstraints()

        # Extract entities to preserve
        constraints.preserve_entities = [e.text for e in sentence.entities]

        # Extract numbers/cardinals to preserve
        constraints.preserve_numbers = [
            t.text for t in sentence.tokens
            if t.upos in {"NUM"} or t.morph.get("NumType") in {"Card", "Ord"}
        ]

        # Select top sense for the root verb
        root = sentence.root_token
        if root and root.i in senses:
            constraints.selected_sense = senses[root.i][0]

        return constraints

    # ------------------------------------------------------------------
    # Step 4: Neural translation
    # ------------------------------------------------------------------

    def _generate_candidates(self, text: str) -> list[NeuralCandidate]:
        if not self._backend.is_available:
            return []
        return self._backend.translate(
            text,
            num_candidates=self._config.num_candidates,
            beam_size=self._config.beam_size,
            max_length=self._config.max_input_length,
        )

    # ------------------------------------------------------------------
    # Step 5: Basic validation
    # ------------------------------------------------------------------

    def _validate_candidate(
        self,
        candidate: NeuralCandidate,
        source_text: str,
        constraints: TranslationConstraints,
        sentence: ParsedSentence,
    ) -> list[TranslationWarning]:
        warnings: list[TranslationWarning] = []
        text = candidate.text

        # Empty output
        if not text.strip():
            warnings.append(TranslationWarning("OTHER", "Empty translation output.", "error"))
            return warnings

        # Unchanged from English (only flag if longer than one word)
        if text.strip().lower() == source_text.strip().lower() and len(source_text.split()) > 1:
            warnings.append(TranslationWarning(
                "UNTRANSLATED_TOKEN", "Output is identical to English source.", "error"
            ))

        # Coordination Agreement validation
        from translator_v2.maltese.validation.agreement import validate_coordination_agreement, validate_subject_verb_agreement  # noqa: PLC0415
        warnings.extend(validate_coordination_agreement(text, sentence))
        warnings.extend(validate_subject_verb_agreement(text, sentence))

        # Untranslated English tokens (rough check)
        source_words = {w.lower() for w in source_text.split() if len(w) > 3}
        output_words = {w.lower().rstrip(".,?!") for w in text.split()}
        untranslated = source_words & output_words
        # Exclude common proper nouns, short words, and words handled by overrides
        from translator_v2.maltese.lexicon.terminology import PREFERRED_TERMS  # noqa: PLC0415
        untranslated = {
            w for w in untranslated
            if w not in {"that", "this", "they", "have", "does"} and w not in PREFERRED_TERMS
        }
        if untranslated:
            for w in sorted(untranslated):
                warnings.append(TranslationWarning(
                    "UNTRANSLATED_TOKEN",
                    f"Possibly untranslated English word: '{w}'",
                    "warning",
                    suggestions=[f"Check Maltese equivalent of '{w}'"],
                ))


        # Named entity preservation
        for entity in constraints.preserve_entities:
            if entity not in text:
                warnings.append(TranslationWarning(
                    "NAMED_ENTITY_ERROR",
                    f"Named entity '{entity}' not found in output.",
                    "warning",
                ))

        # Number preservation
        for number in constraints.preserve_numbers:
            if number not in text:
                warnings.append(TranslationWarning(
                    "NUMBER_PRESERVATION",
                    f"Number '{number}' not found in output.",
                    "warning",
                ))

        return warnings

    # ------------------------------------------------------------------
    # Step 6: Reranking
    # ------------------------------------------------------------------

    def _rerank(
        self,
        candidates: list[TranslationCandidate],
        constraints: TranslationConstraints,
    ) -> list[TranslationCandidate]:
        """Sort candidates: fewer errors/warnings first, higher model score second."""

        def key(c: TranslationCandidate):
            errors = sum(1 for w in c.validation_warnings if w.severity == "error")
            warnings_count = sum(1 for w in c.validation_warnings if w.severity == "warning")
            # Negate score so higher (less negative) is better
            score = -(c.model_score or 0.0)
            return (errors, warnings_count, score)

        sorted_candidates = sorted(candidates, key=key)

        # Annotate ranking reasons on each candidate
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

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, text: str) -> TranslationResult:
        t_start = time.perf_counter()
        pipeline_warnings: list[TranslationWarning] = []

        # Step 1: Parse
        sentence = self._parse(text)
        if not sentence.parser_available:
            for msg in sentence.warnings:
                pipeline_warnings.append(TranslationWarning("PARSER_UNAVAILABLE", msg, "warning"))

        # Step 2: Sense analysis
        senses = self._analyse_senses(sentence)

        # Step 3: Constraints
        constraints = self._build_constraints(sentence, senses)

        # Step 4: Neural translation
        neural_candidates = self._generate_candidates(text)
        if not neural_candidates:
            pipeline_warnings.append(TranslationWarning(
                "BACKEND_UNAVAILABLE",
                f"Backend '{self._config.backend}' returned no candidates.",
                "warning",
            ))

        # Step 5: Build and validate candidates
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

            # Stage 18: Apply deterministic corrections
            from translator_v2.candidates.corrections import apply_candidate_corrections  # noqa: PLC0415
            corrected_variants = apply_candidate_corrections(tc, sentence)
            for cv in corrected_variants:
                # Re-validate the corrected variant (it should now have 0 warnings)
                from translator_v2.neural.base import NeuralCandidate  # noqa: PLC0415
                nc_variant = NeuralCandidate(text=cv.text, score=cv.model_score, source=cv.source)
                cv.validation_warnings = self._validate_candidate(nc_variant, text, constraints, sentence)
                translation_candidates.append(cv)

        # Step 6: Rerank
        ranked = self._rerank(translation_candidates, constraints)

        # Pick best and apply post-processing cleanup
        best_text = ranked[0].text if ranked else ""
        best_text = self._post_process_clean(best_text, text)

        latency = (time.perf_counter() - t_start) * 1000

        return TranslationResult(
            source_text=text,
            translated_text=best_text,
            engine="v2",
            backend=self._backend.name if ranked else None,
            alternatives=ranked,
            warnings=pipeline_warnings,
            metadata={
                "direction": "en-mt",
                "selected_sense": constraints.selected_sense.sense_id if constraints.selected_sense else None,
                "constraints": constraints.to_dict(),
                "parser_available": sentence.parser_available,
                "num_senses_found": sum(len(v) for v in senses.values()),
            },
            latency_ms=latency,
        )

    def _post_process_clean(self, text: str, source: str) -> str:
        """Apply deterministic spacing, punctuation, and casing cleanup."""
        if not text:
            return ""

        import re  # noqa: PLC0415
        cleaned = text.strip()

        # 1. Strip spaces around hyphens: "ix - xogħol" -> "ix-xogħol"
        cleaned = re.sub(r"\s*-\s*", "-", cleaned)

        # 2. Strip spaces around apostrophes: "m' aċċettax" -> "m'aċċettax", "ta' " -> "ta'"
        cleaned = re.sub(r"\s*'\s*", "'", cleaned)
        # Ensure space after apostrophe if it's a preposition/particle (e.g. ma' l-iskola -> ma' l-iskola)
        # but NOT before: "ma' " -> "ma' "
        cleaned = re.sub(r"(\w+')(\w+)", r"\1 \2", cleaned)
        # Fix specific Maltese contractions: "m'-" -> "m'-"
        cleaned = re.sub(r"(\b[fltmbn])'\s+", r"\1'", cleaned)

        # 3. Clean up double spaces
        cleaned = re.sub(r"\s+", " ", cleaned)

        # 4. Sentence Casing: If the source started capitalised, or we are formatting a full sentence,
        # ensure the first letter is capitalised.
        if cleaned and (source[0].isupper() or source.strip().endswith((".", "?", "!")) or len(source.split()) > 1):
            cleaned = cleaned[0].upper() + cleaned[1:]

        # 5. Fix trailing punctuation spacing (e.g. "tiekol ?" -> "tiekol?")
        cleaned = re.sub(r"\s+([.,?!;:])", r"\1", cleaned)

        # 6. Apply terminology overrides (e.g. downstairs -> isfel)
        from translator_v2.maltese.lexicon.terminology import apply_terminology_overrides  # noqa: PLC0415
        cleaned = apply_terminology_overrides(cleaned)

        return cleaned

