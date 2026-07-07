"""
translator_v2/neural/registry.py

Backend registry. Maps backend name strings to backend instances.
Instantiation is lazy — backends are created on first access.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from translator_v2.neural.base import NeuralBackend

_registry: dict[str, "NeuralBackend"] = {}


def get_backend(name: str) -> "NeuralBackend":
    """
    Return a backend by name. Creates and caches on first call.
    Raises ValueError for unknown names.
    """
    if name in _registry:
        return _registry[name]

    if name == "mock":
        from translator_v2.neural.mock import MockBackend  # noqa: PLC0415
        backend = MockBackend()
    elif name == "opus_mt":
        from translator_v2.neural.opus_mt import OpusMTBackend  # noqa: PLC0415
        backend = OpusMTBackend()
    else:
        raise ValueError(
            f"Unknown neural backend: {name!r}. "
            f"Available: 'mock', 'opus_mt'."
        )

    _registry[name] = backend
    return backend


def available_backends() -> list[str]:
    """Return names of all known backends (not necessarily loaded)."""
    return ["mock", "opus_mt"]
