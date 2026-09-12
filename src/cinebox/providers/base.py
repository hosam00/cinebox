"""Provider abstractions and the fallback-chain orchestrator."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

from ..models import StreamInfo
from ..utils import Log

if TYPE_CHECKING:
    from ..models import MediaType


class BaseProvider(abc.ABC):
    """Base class for stream providers.

    A provider maps an IMDb ID (+ optional season/episode) to a StreamInfo,
    or raises an exception when it cannot resolve the stream.
    """

    name: str = "base"

    def __init__(self) -> None:
        self.name = self.__class__.__name__

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
        raise RuntimeError(
            "No provider could resolve this title.\n  "
            + "\n  ".join(errors)
        )
