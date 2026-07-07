from __future__ import annotations

import os
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
FINAL_DICS_DIR = BASE_DIR / "finaldics"
MAX_TEXT_LENGTH = 10_000

app = Flask(__name__)

ENABLE_DEV_TOOLS = False

# ---------------------------------------------------------------------------
# Engine selection
# TRANSLATOR_ENGINE=v2    → use the new hybrid v2 pipeline (default)
# TRANSLATOR_ENGINE=legacy → use the original MalteseTranslator
# ---------------------------------------------------------------------------
_TRANSLATOR_ENGINE = os.getenv("TRANSLATOR_ENGINE", "v2").strip().lower()

_startup_started = time.perf_counter()
if _TRANSLATOR_ENGINE == "legacy":
    from Essentials.translator import MalteseTranslator
    from Essentials.ai_assist import ai_enabled, ai_key_present, ai_provider
    translator = MalteseTranslator(FINAL_DICS_DIR)
    _engine_label = "legacy"
else:
    from translator_v2 import V2Engine
    from Essentials.ai_assist import ai_enabled, ai_key_present, ai_provider
    translator = V2Engine()
    _engine_label = "v2"

print(f"Translator loaded [{_engine_label}] in {(time.perf_counter() - _startup_started) * 1000:.1f} ms.")


@app.get("/")
def home():
    html_path = BASE_DIR / "index.html"
    try:
        html = html_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "index.html not found", 404

    html = html.replace(
        '"REPLACE_ME_ENABLE_DEV_TOOLS" === "True"',
        "true" if ENABLE_DEV_TOOLS else "false",
    )
    return html


@app.get("/devtoy.js")
def devtoy_js():
    return send_from_directory(BASE_DIR, "devtoy.js")


@app.get("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(BASE_DIR / "assets", filename)


@app.get("/devtoy-assets/<filename>")
def devtoy_assets(filename):
    return send_from_directory(BASE_DIR / "assets" / "devtoys", filename)


@app.get("/health")
def health():
    return jsonify(
        {
            "ok": True,
            "status": "ok",
            "mode": "translator",
            "engine": _engine_label,
            "english_entries": len(getattr(translator, "en_to_mt", {})),
            "maltese_entries": len(getattr(translator, "mt_to_en", {})),
            "devtools_enabled": ENABLE_DEV_TOOLS,
            "ai_enabled": ai_enabled(),
            "ai_provider": ai_provider(),
            "ai_key_present": ai_key_present(),
            "openai_key_present": bool(os.getenv("OPENAI_API_KEY")),
            "gemini_key_present": bool(os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")),
        }
    )


@app.post("/translate")
def translate():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    direction = data.get("direction", "en-mt")

    if not isinstance(text, str):
        return jsonify({"error": "text must be a string."}), 400
    if not text.strip():
        return jsonify({"error": "Please write some text first."}), 400
    if len(text) > MAX_TEXT_LENGTH:
        return jsonify({"error": f"Text is too long. Maximum length is {MAX_TEXT_LENGTH} characters."}), 413

    result = translator.translate(text, direction=direction)

    # Build response — always include legacy fields; add v2 fields when available
    response: dict = {
        "input": result.input if hasattr(result, "input") else text,
        "direction": result.direction if hasattr(result, "direction") else direction,
        "translated_text": result.translated_text,
        "candidates": result.candidates if hasattr(result, "candidates") else [],
        "suggestions": result.suggestions if hasattr(result, "suggestions") else [],
        "highlights": result.highlights if hasattr(result, "highlights") else [],
        "notes": result.notes if hasattr(result, "notes") else [],
        "engine": _engine_label,
    }
    # v2-only fields
    if hasattr(result, "backend") and result.backend:
        response["backend"] = result.backend
    if hasattr(result, "warnings") and result.warnings:
        response["warnings"] = [
            w.to_dict() if hasattr(w, "to_dict") else str(w)
            for w in result.warnings
        ]
    if hasattr(result, "latency_ms") and result.latency_ms is not None:
        response["latency_ms"] = round(result.latency_ms, 2)
    if hasattr(result, "metadata") and result.metadata:
        selected_sense = result.metadata.get("selected_sense")
        if selected_sense:
            response["selected_sense"] = selected_sense

    return jsonify(response)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5001)),
        debug=False,
        use_reloader=False,
    )


