from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge

from translator_v2.configuration import ConfigurationError, V2Config

BASE_DIR = Path(__file__).resolve().parent
FINAL_DICS_DIR = BASE_DIR / "finaldics"
TRUE_VALUES = {"1", "true", "yes", "on"}
VALID_DIRECTIONS = {"en-mt", "mt-en"}

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

ENABLE_DEV_TOOLS = os.getenv("ENABLE_DEV_TOOLS", "").strip().casefold() in TRUE_VALUES
MAX_TEXT_LENGTH = int(os.getenv("MAX_TEXT_LENGTH", "2000"))
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(MAX_TEXT_LENGTH * 4)))


def _safe_error(message: str, status_code: int):
    return jsonify({"ok": False, "error": message}), status_code


def _build_translator() -> tuple[Any, str, str]:
    engine = os.getenv("TRANSLATOR_ENGINE", "v2").strip().casefold()
    started = time.perf_counter()
    if engine == "legacy":
        from Essentials.translator import MalteseTranslator  # noqa: PLC0415
        translator = MalteseTranslator(FINAL_DICS_DIR)
        logger.warning("translator initialized engine=legacy ms=%.2f", (time.perf_counter() - started) * 1000)
        return translator, "legacy", "rules"

    if engine != "v2":
        raise ConfigurationError("TRANSLATOR_ENGINE must be one of: legacy, v2")

    from translator_v2 import V2Engine  # noqa: PLC0415
    config = V2Config.from_env()
    translator = V2Engine(config)
    timings = translator.initialize()
    logger.warning(
        "translator initialized engine=v2 backend=%s ms=%.2f timings=%s",
        config.backend,
        (time.perf_counter() - started) * 1000,
        timings,
    )
    return translator, "v2", config.backend


def _legacy_ready(translator: Any, engine_label: str, backend_label: str) -> dict[str, Any]:
    if hasattr(translator, "ready_status"):
        return translator.ready_status()
    return {
        "ok": True,
        "status": "ready",
        "engine": engine_label,
        "backend": backend_label,
        "spacy_ready": engine_label != "v2",
        "opus_ready": backend_label not in {"hybrid", "opus_mt"},
        "core_resources_ready": True,
    }


def _result_response(result: Any, text: str, direction: str, engine_label: str) -> dict[str, Any]:
    response: dict[str, Any] = {
        "input": result.input if hasattr(result, "input") else text,
        "direction": result.direction if hasattr(result, "direction") else direction,
        "translated_text": result.translated_text,
        "candidates": result.candidates if hasattr(result, "candidates") else [],
        "suggestions": result.suggestions if hasattr(result, "suggestions") else [],
        "highlights": result.highlights if hasattr(result, "highlights") else [],
        "notes": result.notes if hasattr(result, "notes") else [],
        "engine": engine_label,
    }
    if getattr(result, "backend", None):
        response["backend"] = result.backend
    if getattr(result, "warnings", None):
        response["warnings"] = [w.to_dict() if hasattr(w, "to_dict") else str(w) for w in result.warnings]
    if getattr(result, "latency_ms", None) is not None:
        response["latency_ms"] = round(result.latency_ms, 2)
    metadata = getattr(result, "metadata", {}) or {}
    for key in ("selected_sense", "opus_translation", "rule_changes", "timings_ms"):
        value = metadata.get(key)
        if value:
            response[key] = value
    return response


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

    try:
        translator, engine_label, backend_label = _build_translator()
        startup_error = ""
    except Exception as exc:  # noqa: BLE001
        translator = None
        engine_label = os.getenv("TRANSLATOR_ENGINE", "v2").strip().casefold()
        backend_label = os.getenv("TRANSLATION_BACKEND", "hybrid").strip().casefold()
        startup_error = str(exc)
        logger.exception("translator startup failed")

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_error):
        return _safe_error(f"Text is too long. Maximum length is {MAX_TEXT_LENGTH} characters.", 413)

    @app.get("/")
    def home():
        html_path = BASE_DIR / "index.html"
        try:
            html = html_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return "index.html not found", 404
        html = html.replace('"REPLACE_ME_ENABLE_DEV_TOOLS" === "True"', "true" if ENABLE_DEV_TOOLS else "false")
        return html

    if ENABLE_DEV_TOOLS:
        @app.get("/devtoy.js")
        def devtoy_js():
            return send_from_directory(BASE_DIR, "devtoy.js")

        @app.get("/devtoy-assets/<filename>")
        def devtoy_assets(filename):
            return send_from_directory(BASE_DIR / "assets" / "devtoys", filename)

    @app.get("/assets/<path:filename>")
    def assets(filename):
        return send_from_directory(BASE_DIR / "assets", filename)

    @app.get("/health")
    def health():
        return jsonify({"ok": True, "status": "alive"})

    @app.get("/ready")
    def ready():
        if translator is None:
            return jsonify({
                "ok": False,
                "status": "not_ready",
                "engine": engine_label,
                "backend": backend_label,
                "spacy_ready": False,
                "opus_ready": False,
                "core_resources_ready": False,
                "initialization_error": startup_error,
            }), 503
        status = _legacy_ready(translator, engine_label, backend_label)
        return jsonify(status), 200 if status.get("ok") else 503

    @app.post("/translate")
    def translate():
        if translator is None:
            return _safe_error("Translation resources are not available.", 503)

        if not request.is_json:
            return _safe_error("Request body must be JSON.", 400)
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return _safe_error("JSON body must be an object.", 400)

        text = data.get("text", "")
        direction = data.get("direction", "en-mt")
        if not isinstance(text, str):
            return _safe_error("text must be a string.", 400)
        if not isinstance(direction, str):
            return _safe_error("direction must be a string.", 400)
        if direction not in VALID_DIRECTIONS:
            return _safe_error("direction must be exactly 'en-mt' or 'mt-en'.", 400)
        if not text.strip():
            return _safe_error("Please write some text first.", 400)
        if len(text) > MAX_TEXT_LENGTH:
            return _safe_error(f"Text is too long. Maximum length is {MAX_TEXT_LENGTH} characters.", 413)

        if hasattr(translator, "supports_direction") and not translator.supports_direction(direction):
            return _safe_error(f"Direction '{direction}' is not implemented by this engine.", 501)

        ready_status = _legacy_ready(translator, engine_label, backend_label)
        if not ready_status.get("ok"):
            return _safe_error("Translation resources are still initializing or unavailable.", 503)

        started = time.perf_counter()
        try:
            result = translator.translate(text, direction=direction)
        except RuntimeError as exc:
            logger.exception("translation resource failure")
            return _safe_error(str(exc) or "Translation resources are unavailable.", 503)
        except Exception:  # noqa: BLE001
            logger.exception("unexpected translation failure")
            return _safe_error("Internal translation error.", 500)

        logger.warning(
            "translate request chars=%s direction=%s engine=%s backend=%s total_ms=%.2f",
            len(text),
            direction,
            engine_label,
            backend_label,
            (time.perf_counter() - started) * 1000,
        )
        return jsonify(_result_response(result, text, direction, engine_label))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5001)),
        debug=False,
        use_reloader=False,
    )
