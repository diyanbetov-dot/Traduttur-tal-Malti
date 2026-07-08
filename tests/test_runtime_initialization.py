from __future__ import annotations

import importlib
from concurrent.futures import ThreadPoolExecutor

import pytest

from translator_v2.configuration import ConfigurationError, V2Config
from translator_v2.engine import V2Engine
from translator_v2.neural.opus_mt import OpusMTBackend
from translator_v2.neural.registry import get_backend


def test_config_defaults_to_hybrid_quality_settings(monkeypatch):
    monkeypatch.delenv("TRANSLATION_BACKEND", raising=False)
    config = V2Config.from_env()
    assert config.backend == "hybrid"
    assert config.requires_opus is True
    assert config.num_candidates == 5
    assert config.beam_size == 5


def test_config_rejects_unknown_backend(monkeypatch):
    monkeypatch.setenv("TRANSLATION_BACKEND", "surprise")
    with pytest.raises(ConfigurationError):
        V2Config.from_env()


def test_hybrid_registry_uses_opus_backend_without_loading_model():
    backend = get_backend("hybrid", cache_dir="test-cache-marker", model_dir="test-model-marker", local_files_only=True)
    assert isinstance(backend, OpusMTBackend)
    assert backend.name == "opus_mt"
    assert backend.status.ready is False


def test_mock_engine_initializes_once_under_concurrency():
    engine = V2Engine(V2Config(backend="mock", preload_spacy=False, preload_opus=False))
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _i: engine.initialize(), range(16)))
    assert all(r["backend_mode"] == "mock" for r in results)
    assert engine.ready_status()["ok"] is True


def test_v2_rejects_mt_en_as_unsupported():
    engine = V2Engine(V2Config(backend="mock", preload_spacy=False, preload_opus=False))
    assert engine.supports_direction("mt-en") is False
    assert engine.supports_direction("en-mt") is True


def test_flask_health_ready_and_validation(monkeypatch):
    monkeypatch.setenv("TRANSLATION_BACKEND", "mock")
    monkeypatch.setenv("PRELOAD_SPACY", "false")
    monkeypatch.setenv("PRELOAD_OPUS", "false")
    import Essentials.app as app_module
    importlib.reload(app_module)
    client = app_module.app.test_client()

    health = client.get("/health")
    assert health.status_code == 200
    assert health.get_json() == {"ok": True, "status": "alive"}
    assert "key" not in " ".join(health.get_json().keys())

    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.get_json()["backend"] == "mock"

    assert client.post("/translate", data="not-json", content_type="text/plain").status_code == 400
    assert client.post("/translate", json={"text": "Hello", "direction": "bad"}).status_code == 400
    assert client.post("/translate", json={"text": "Hello", "direction": "mt-en"}).status_code == 501
