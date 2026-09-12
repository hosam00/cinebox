"""Provider registry and orchestration."""

from __future__ import annotations

from .base import BaseProvider, ProviderRegistry
from .imdb_su import ImdbSuProvider
from .multiembed import MultiEmbedProvider
from .vidsrc import VidSrcProvider

__all__ = [
    "BaseProvider",
    "ProviderRegistry",
    "ImdbSuProvider",
    "MultiEmbedProvider",
    "VidSrcProvider",
]


def build_registry() -> ProviderRegistry:
    """Create a registry with all providers in priority order."""
    registry = ProviderRegistry()
    registry.register(ImdbSuProvider())
    registry.register(VidSrcProvider())
    registry.register(MultiEmbedProvider())
    return registry
