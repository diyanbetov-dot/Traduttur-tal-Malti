from __future__ import annotations

import os
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from Essentials.translator import MalteseTranslator
from Essentials.ai_assist import ai_enabled, ai_key_present, ai_provider


BASE_DIR = Path(__file__).resolve().parent
FINAL_DICS_DIR = BASE_DIR / "finaldics"
MAX_TEXT_LENGTH = 10_000

app = Flask(__name__)

_startup_started = time.perf_counter()
translator = MalteseTranslator(FINAL_DICS_DIR)
print(f"Translator loaded in {(time.perf_counter() - _startup_started) * 1000:.1f} ms.")

ENABLE_DEV_TOOLS = False


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
            "english_entries": len(translator.en_to_mt),
            "maltese_entries": len(translator.mt_to_en),
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
    return jsonify(
        {
            "input": result.input,
            "direction": result.direction,
            "translated_text": result.translated_text,
            "candidates": result.candidates,
            "suggestions": result.suggestions,
            "highlights": result.highlights,
            "notes": result.notes,
        }
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5001)),
        debug=False,
        use_reloader=False,
    )


