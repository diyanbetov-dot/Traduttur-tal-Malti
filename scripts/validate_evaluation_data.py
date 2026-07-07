"""
scripts/validate_evaluation_data.py

Validates a JSONL evaluation data file.

Usage:
    python scripts/validate_evaluation_data.py data/evaluation/development.jsonl
    python scripts/validate_evaluation_data.py data/evaluation/development.jsonl --strict

Exit code 0 = no errors. Exit code 1 = validation failed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VALID_CATEGORIES = frozenset({
    "lexical_ambiguity", "simple_present", "simple_past", "progressive", "modal",
    "negation", "question", "complement_chain", "transitive", "intransitive",
    "copula", "noun_phrase", "adjective_agreement", "verb_agreement", "clitic",
    "article", "preposition", "possessive", "phrasal_verb", "named_entity",
    "number", "register", "idiom", "word_order", "coordination",
})

VALID_STATUSES = frozenset({"needs_human_review", "machine_suggested", "reviewed", "verified"})

REQUIRED_FIELDS = {"id", "source_en", "reference_mt", "alternative_references_mt", "category", "review_status"}


def validate_file(path: Path, strict: bool = False) -> list[str]:
    """Return list of error messages. Empty = valid."""
    errors: list[str] = []

    if not path.exists():
        return [f"File not found: {path}"]

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [f"UTF-8 decode error: {exc}"]

    seen_ids: set[str] = set()

    for lineno, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue

        # Parse
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"Line {lineno}: JSON parse error: {exc}")
            continue

        if not isinstance(record, dict):
            errors.append(f"Line {lineno}: Expected JSON object, got {type(record).__name__}")
            continue

        # Required fields
        for field in REQUIRED_FIELDS:
            if field not in record:
                errors.append(f"Line {lineno}: Missing required field: {field!r}")

        # ID uniqueness
        record_id = record.get("id", "")
        if not record_id:
            errors.append(f"Line {lineno}: Empty or missing 'id'")
        elif record_id in seen_ids:
            errors.append(f"Line {lineno}: Duplicate ID: {record_id!r}")
        else:
            seen_ids.add(record_id)

        # Non-empty source
        source = record.get("source_en", "")
        if not source or not source.strip():
            errors.append(f"Line {lineno} ({record_id}): 'source_en' is empty")

        # reference_mt may be empty (needs_human_review), but must be a string
        ref = record.get("reference_mt", None)
        if ref is not None and not isinstance(ref, str):
            errors.append(f"Line {lineno} ({record_id}): 'reference_mt' must be a string")

        # alternative_references_mt must be a list
        alts = record.get("alternative_references_mt", None)
        if alts is not None and not isinstance(alts, list):
            errors.append(f"Line {lineno} ({record_id}): 'alternative_references_mt' must be a list")

        # category must be a non-empty list of valid strings
        cats = record.get("category", [])
        if not isinstance(cats, list) or not cats:
            errors.append(f"Line {lineno} ({record_id}): 'category' must be a non-empty list")
        else:
            for cat in cats:
                if cat not in VALID_CATEGORIES:
                    errors.append(
                        f"Line {lineno} ({record_id}): Unknown category: {cat!r}. "
                        f"Valid: {sorted(VALID_CATEGORIES)}"
                    )

        # review_status
        status = record.get("review_status", "")
        if status not in VALID_STATUSES:
            errors.append(f"Line {lineno} ({record_id}): Invalid review_status: {status!r}")

        # Strict mode: reference_mt must be non-empty if reviewed/verified
        if strict and status in {"reviewed", "verified"}:
            ref_val = record.get("reference_mt", "")
            if not ref_val or not ref_val.strip():
                errors.append(
                    f"Line {lineno} ({record_id}): review_status={status!r} "
                    "but reference_mt is empty (--strict mode requires a reference)"
                )

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an evaluation JSONL file.")
    parser.add_argument("file", help="Path to the JSONL file.")
    parser.add_argument("--strict", action="store_true",
                        help="Require reference_mt to be non-empty for reviewed/verified entries.")
    args = parser.parse_args()

    path = Path(args.file)
    errors = validate_file(path, strict=args.strict)

    if errors:
        print(f"❌ Validation FAILED ({len(errors)} error(s)):")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        # Count lines
        lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        print(f"✅ Validation passed. {len(lines)} valid record(s) in {path.name}.")


if __name__ == "__main__":
    main()
