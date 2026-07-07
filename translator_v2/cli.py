"""
translator_v2/cli.py

Command-line interface for the v2 translator.

Usage:
    python -m translator_v2.cli "She runs a successful company."
    python -m translator_v2.cli "She runs every morning." --backend mock
    python -m translator_v2.cli "The lion is big." --backend opus_mt
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Translate English to Maltese using the v2 hybrid engine."
    )
    parser.add_argument("text", help="English text to translate.")
    parser.add_argument(
        "--backend", default=None,
        help="Neural backend: mock (default), opus_mt. Overrides TRANSLATION_BACKEND env var."
    )
    parser.add_argument(
        "--candidates", type=int, default=3,
        help="Number of neural candidates to generate (default: 3)."
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output full JSON result instead of human-readable summary."
    )
    args = parser.parse_args(argv)

    if args.backend:
        os.environ["TRANSLATION_BACKEND"] = args.backend
    os.environ["TRANSLATION_NUM_CANDIDATES"] = str(args.candidates)
    os.environ["TRANSLATOR_ENGINE"] = "v2"

    from translator_v2 import V2Engine  # noqa: PLC0415
    engine = V2Engine()
    result = engine.translate(args.text, direction="en-mt")

    if args.json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return

    print(f"\n{'='*60}")
    print(f"  Source:    {result.source_text}")
    print(f"  Output:    {result.translated_text}")
    print(f"  Engine:    {result.engine}")
    print(f"  Backend:   {result.backend}")
    if result.latency_ms is not None:
        print(f"  Latency:   {result.latency_ms:.1f} ms")

    sense = result.metadata.get("selected_sense")
    if sense:
        print(f"  Sense:     {sense}")

    parser_ok = result.metadata.get("parser_available", False)
    print(f"  Parser:    {'spaCy' if parser_ok else 'unavailable'}")

    if result.warnings:
        print(f"\n  Warnings ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"    [{w.severity.upper()}] {w.code}: {w.message}")

    if result.alternatives:
        print(f"\n  Candidates ({len(result.alternatives)}):")
        for i, c in enumerate(result.alternatives):
            marker = "→" if i == 0 else " "
            score_str = f" (score: {c.model_score:.3f})" if c.model_score is not None else ""
            warn_str = f" [{c.error_count}E {c.warning_count}W]" if c.validation_warnings else ""
            print(f"    {marker} [{i+1}] {c.text}{score_str}{warn_str}")
            if c.ranking_reasons:
                print(f"          Reasons: {', '.join(c.ranking_reasons)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
