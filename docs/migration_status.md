# Migration Status

## Legend
- ✅ Done
- 🔄 In progress
- ⏳ Planned
- ❌ Blocked

---

## Stage 1 — Repository Audit
- ✅ `docs/current_architecture.md` — Full flow diagram, class index, pattern catalogue
- ✅ `docs/resource_inventory.md` — All 13 data files with line counts, schemas, consumers
- ✅ `docs/maltese_data_needed.md` — 22 unresolved linguistic questions catalogued

## Stage 2 — Legacy Preservation
- ✅ `legacy/__init__.py`
- ✅ `legacy/translator_v1.py` — Re-exports MalteseTranslator; legacy code untouched
- ✅ `legacy/tests/test_legacy_basics.py` — 18 regression tests
- ✅ `Essentials/app.py` — TRANSLATOR_ENGINE env routing added (legacy/v2)
- ✅ Legacy engine default available via `TRANSLATOR_ENGINE=legacy`

## Stage 3 — Evaluation Framework
- ✅ `data/evaluation/README.md` — Schema, category list, result format
- ✅ `data/evaluation/development.jsonl` — 25 entries with human-reviewed Maltese references
- ✅ `data/evaluation/test.jsonl` — Empty scaffold (locked)
- ✅ `scripts/validate_evaluation_data.py` — Validation script (25/25 pass)

## Stage 4 — v2 Package Skeleton
- ✅ `translator_v2/__init__.py`
- ✅ `translator_v2/engine.py` — V2Engine, Flask-compatible translate()
- ✅ `translator_v2/pipeline.py` — Full orchestration pipeline
- ✅ `translator_v2/configuration.py` — Env-var-driven V2Config
- ✅ `translator_v2/result.py` — TranslationResult, TranslationCandidate, TranslationWarning
- ✅ `translator_v2/cli.py` — CLI for testing
- ✅ All subpackage `__init__.py` files created

## Stage 5 — English Parser Adapter
- ✅ `translator_v2/source_analysis/models.py` — Token, ParsedSentence dataclasses
- ✅ `translator_v2/source_analysis/base.py` — Abstract EnglishParser interface
- ✅ `translator_v2/source_analysis/english_parser.py` — SpacyParser with graceful fallback
- ✅ `translator_v2/source_analysis/semantic_classes.py` — Semantic class taxonomy
- ⏳ spaCy installed in venv — pending `python -m spacy download en_core_web_sm`

## Stage 6 — Lexical Sense Data Models
- ✅ `translator_v2/lexical_sense/models.py` — SenseRecord dataclass
- ✅ `translator_v2/lexical_sense/resolver.py` — Sense ranking by dep/transitivity/collocation
- ✅ `translator_v2/lexical_sense/data/run.jsonl` — 7 senses (Maltese lemmas: needs_human_review)
- ✅ `translator_v2/lexical_sense/data/bank.jsonl` — 3 senses
- ✅ `translator_v2/lexical_sense/data/book.jsonl` — 2 senses
- ⏳ Maltese lemma verification — 6 confirmed by user, 6 remaining

## Stage 7 — Pre-translation Constraints
- ✅ `TranslationConstraints` dataclass in `pipeline.py`
- ✅ Entity preservation checks
- ✅ Number preservation checks
- ⏳ Preferred Maltese lemma constraints (waiting on verified senses)

## Stage 8 — Neural Backend
- ✅ `translator_v2/neural/base.py` — Abstract NeuralBackend
- ✅ `translator_v2/neural/mock.py` — MockBackend (no download)
- ✅ `translator_v2/neural/registry.py` — Lazy backend registry
- ✅ `translator_v2/neural/opus_mt.py` — OPUS-MT adapter (stub, lazy-loads on first use)
- ⏳ OPUS-MT model download (~300 MB) — opt-in, not automatic

## Stage 9 — Flask Integration
- ✅ `Essentials/app.py` — v2 engine default, legacy available via env var
- ✅ Response includes `engine`, `backend`, `warnings`, `latency_ms`, `selected_sense`
- ✅ Legacy response fields preserved (input, direction, candidates, suggestions, highlights, notes)

## Stage 10 — Maltese Data Questions
- ✅ `docs/maltese_data_needed.md` — 22 entries
- ⏳ 6 confirmed by user in eval session; remaining need verification

## Tests
- ✅ `tests/neural/test_mock_backend.py` — 9 unit tests
- ✅ `tests/lexical_sense/test_sense_models.py` — 4 unit tests
- ✅ `tests/lexical_sense/test_run_senses.py` — 5 integration tests
- ✅ `legacy/tests/test_legacy_basics.py` — 18 regression tests
- ⏳ pytest installed in venv

## Next Stages (Planned)
- ⏳ Stage 11 — Maltese Lexicon Database (import from existing .dic files)
- ⏳ Stage 12 — Morphology Modules (articles, verbs, nouns, adjectives, clitics)
- ⏳ Stage 13 — Morphological Validator
- ⏳ Stage 14 — Corpus Importer (migrate verb paradigm .dic files)
- ⏳ Stage 15 — spaCy integration and OPUS-MT model download
- ⏳ Stage 16 — Full evaluation run against all 25 development sentences
- ⏳ Stage 17 — Verified sense files with confirmed Maltese lemmas
- ⏳ Stage 18 — Human review workflow
