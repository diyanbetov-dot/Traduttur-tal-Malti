"""
translator_v2/neural/registry.py

Thread-safe backend registry. Backends are constructed once per process and reused.
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from translator_v2.neural.base import NeuralBackend

_registry: dict[tuple[str, str, str, bool], "NeuralBackend"] = {}
_registry_lock = threading.Lock()


def get_backend(
    name: str,
    *,
    cache_dir: str | None = None,
    model_dir: str | None = None,
    model_name: str | None = None,
    local_files_only: bool = False,
) -> "NeuralBackend":
    """Return a cached backend by validated name."""
    normalized = name.strip().casefold()
    backend_name = "opus_mt" if normalized == "hybrid" else "mock" if normalized == "rules" else normalized
    key = (backend_name, cache_dir or "", model_dir or "", bool(local_files_only))

    with _registry_lock:
        if key in _registry:
            return _registry[key]

        if backend_name == "mock":
            from translator_v2.neural.mock import MockBackend  # noqa: PLC0415
            backend = MockBackend()
        elif backend_name == "opus_mt":
            from translator_v2.neural.opus_mt import OpusMTBackend  # noqa: PLC0415
            kwargs = {
                "cache_dir": cache_dir,
                "model_dir": model_dir,
                "local_files_only": local_files_only,
            }
            if model_name:
                kwargs["model_name"] = model_name
            backend = OpusMTBackend(**kwargs)
        else:
            raise ValueError(
                f"Unknown neural backend: {name!r}. Available: 'hybrid', 'opus_mt', 'rules', 'mock'."
            )

        _registry[key] = backend
        return backend


def available_backends() -> list[str]:
    return ["hybrid", "opus_mt", "rules", "mock"]
