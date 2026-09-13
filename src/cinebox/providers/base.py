"""Provider abstractions and the fallback-chain orchestrator."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

from ..models import StreamInfo
from ..utils import Log, ProviderError

if TYPE_CHECKING:
    from ..models import MediaType, SearchResult


class BaseProvider(abc.ABC):
    """Base class for stream providers.

    A provider maps an IMDb ID (+ optional season/episode) to a StreamInfo,
    or raises an exception when it cannot resolve the stream.

    ``priority`` sets the position in the fallback chain when providers are
    auto-discovered (lower runs first). ``name`` identifies the provider in
    history/logs and must be unique across all providers.
    """

    name: str = "base"
    priority: int = 100

    def __init__(self) -> None:
        self.name = self.__class__.name

    @abc.abstractmethod
    def resolve(
        self,
        imdb_id: str,
        media_type: MediaType,
        season: int | None = None,
        episode: int | None = None,
    ) -> StreamInfo:
        """Resolve a playable stream URL for the given title."""

    def __repr__(self) -> str:
        return f"<{self.name}>"


class ResolutionError(ProviderError):
    """Raised when the whole provider chain fails to resolve a stream.

    ``errors`` carries one message per attempted provider so the UI can
    show exactly why each source failed.
    """

    def __init__(self, errors: list[str] | None = None) -> None:
        self.errors = list(errors or [])
        detail = "\n".join(f"  ✗ {e}" for e in self.errors) or "  no provider attempted"
        super().__init__(f"No provider could resolve this title.\n{detail}")


class ProviderRegistry:
    """Holds all providers in priority order and resolves via fallback chain."""

    def __init__(self, providers: list[BaseProvider] | None = None) -> None:
        self.providers: list[BaseProvider] = providers or []

    def register(self, provider: BaseProvider) -> None:
        if any(p.name == provider.name for p in self.providers):
            Log.debug(f"Provider {provider.name!r} already registered, skipping.")
            return
        self.providers.append(provider)

    def names(self) -> list[str]:
        return [p.name for p in self.providers]

    def resolve(
        self,
        imdb_id: str,
        media_type: MediaType,
        season: int | None = None,
        episode: int | None = None,
        fail_fast: bool = False,
    ) -> StreamInfo:
        """Try each provider in order until one resolves a stream."""
        errors: list[str] = []
        for provider in self.providers:
            Log.info(f"Resolving via {provider.name}...")
            try:
                stream = provider.resolve(imdb_id, media_type, season, episode)
                Log.info(f"Stream resolved by {provider.name}: {stream.url[:60]}...")
                return stream
            except Exception as e:  # noqa: BLE001 - provider errors are expected
                errors.append(f"{provider.name}: {e}")
                Log.warn(f"{provider.name} failed: {e}")
                if fail_fast:
                    break
        raise ResolutionError(errors)

    def keyword_providers(self) -> list[BaseProvider]:
        """Providers that implement ``search(query, media_type)``."""
        return [p for p in self.providers if callable(getattr(p, "search", None))]

    def search(
        self,
        query: str,
        media_type: MediaType | None = None,
    ) -> list[SearchResult]:
        """Merge keyword-search results from all keyword-capable providers.

        Results are deduplicated by ``imdb_id``, preserving provider
        order (first hit for an ID wins). Failures are logged and skipped
        so one broken source never blocks the others.
        """
        results: list[SearchResult] = []
        seen: set[str] = set()
        for provider in self.keyword_providers():
            Log.info(f"Searching '{query}' via {provider.name}...")
            try:
                found = provider.search(query, media_type)
            except Exception as e:  # noqa: BLE001 - isolated per provider
                Log.warn(f"{provider.name} search failed: {e}")
                continue
            for result in found:
                if result.imdb_id in seen:
                    continue
                seen.add(result.imdb_id)
                results.append(result)
        return results
