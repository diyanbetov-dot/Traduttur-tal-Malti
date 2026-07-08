from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from translator_v2.configuration import V2Config
from translator_v2.engine import V2Engine

SENTENCES = [
    "I went swimming yesterday.",
    "She runs a company.",
    "They were waiting outside.",
    "I would have gone if I had known.",
]


def _memory_mb() -> float | None:
    try:
        import psutil  # type: ignore
        process = psutil.Process(os.getpid())
        return round(process.memory_info().rss / (1024 * 1024), 2)
    except Exception:
        return None


def _time_call(fn):
    started = time.perf_counter()
    value = fn()
    return value, round((time.perf_counter() - started) * 1000, 2)


def main() -> int:
    report: dict[str, Any] = {
        "sentences": SENTENCES,
        "memory_before_mb": _memory_mb(),
    }

    config, config_ms = _time_call(V2Config.from_env)
    report["config_ms"] = config_ms
    report["config"] = {
        "engine": config.engine,
        "backend": config.backend,
        "preload_spacy": config.preload_spacy,
        "preload_opus": config.preload_opus,
        "rule_postprocessing_enabled": config.rule_postprocessing_enabled,
        "num_candidates": config.num_candidates,
        "beam_size": config.beam_size,
        "local_files_only": config.local_files_only,
    }

    engine, engine_ms = _time_call(lambda: V2Engine(config))
    report["engine_create_ms"] = engine_ms
    report["memory_after_engine_mb"] = _memory_mb()

    init_result, init_ms = _time_call(engine.initialize)
    report["initialize_call_ms"] = init_ms
    report["initialize"] = init_result
    report["ready"] = engine.ready_status()
    report["memory_after_initialize_mb"] = _memory_mb()

    translations = []
    for sentence in SENTENCES:
        result, elapsed_ms = _time_call(lambda s=sentence: engine.translate(s, direction="en-mt"))
        translations.append({
            "source": sentence,
            "elapsed_ms": elapsed_ms,
            "backend": result.backend,
            "opus_translation": result.metadata.get("opus_translation"),
            "translated_text": result.translated_text,
            "timings_ms": result.metadata.get("timings_ms", {}),
        })
    report["translations"] = translations
    report["memory_after_translations_mb"] = _memory_mb()

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
