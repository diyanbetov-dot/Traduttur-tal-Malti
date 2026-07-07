# Evaluation Data

## Purpose

This directory contains sentence pairs for evaluating Maltese translation engines.

- `development.jsonl` — working set used during development for rapid iteration
- `test.jsonl` — locked set used only for final evaluation (do not inspect during development)
- `results/` — engine output files, one per run

## Schema

```json
{
  "id": "eval-001",
  "source_en": "She runs a successful company.",
  "reference_mt": "",
  "alternative_references_mt": [],
  "category": ["lexical_ambiguity", "simple_present"],
  "notes": "",
  "review_status": "needs_human_review"
}
```

### Fields

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier, format `eval-NNN` |
| `source_en` | string | English source sentence (required, non-empty) |
| `reference_mt` | string | Primary Maltese reference (empty until human-reviewed) |
| `alternative_references_mt` | array | Accepted alternative translations |
| `category` | array | Error/feature categories (see list below) |
| `notes` | string | Free-text notes for reviewers |
| `review_status` | string | `needs_human_review` \| `reviewed` \| `verified` |

### Valid Categories

`lexical_ambiguity`, `simple_present`, `simple_past`, `progressive`, `modal`,
`negation`, `question`, `complement_chain`, `transitive`, `intransitive`,
`copula`, `noun_phrase`, `adjective_agreement`, `verb_agreement`, `clitic`,
`article`, `preposition`, `possessive`, `phrasal_verb`, `named_entity`,
`number`, `register`, `idiom`, `word_order`

## How to Add Entries

1. Choose the next available `id` (check the last line of `development.jsonl`)
2. Write the English source in `source_en`
3. Leave `reference_mt` empty or write your translation
4. Set `review_status` to `needs_human_review` if not yet verified
5. Run `python scripts/validate_evaluation_data.py data/evaluation/development.jsonl`

## Result Files

Stored in `results/`. Format: one JSON object per line:
```json
{
  "id": "eval-001",
  "source_en": "...",
  "engine": "legacy|v2|opus_mt",
  "backend": "mock|opus_mt|nllb",
  "translated_text": "...",
  "warnings": [],
  "latency_ms": 42.1,
  "run_id": "2026-07-07T21:00:00Z"
}
```
