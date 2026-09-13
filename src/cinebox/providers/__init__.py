"""Provider registry and orchestration."""

from __future__ import annotations

from .base import BaseProvider, ProviderRegistry, ResolutionError
from .discovery import build_providers, iter_provider_classes
from .imdb_su import ImdbSuProvider
from .keyword import KeywordProvider
from .multiembed import MultiEmbedProvider
from .vidsrc import VidSrcProvider

__all__ = [
    "BaseProvider",
    "ProviderRegistry",
    "ResolutionError",
    "KeywordProvider",
    "ImdbSuProvider",
    "MultiEmbedProvider",
    "VidSrcProvider",
    "build_providers",
    "iter_provider_classes",
]


def build_registry() -> ProviderRegistry:
    """Create a registry with all auto-discovered providers in priority order."""
    return ProviderRegistry(build_providers())
