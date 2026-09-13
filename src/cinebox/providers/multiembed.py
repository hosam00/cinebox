"""Fallback provider: multiembed.mov / streamingnow.mov.

multiembed.mov redirects to streamingnow.mov behind Cloudflare Turnstile
and heavily obfuscated JS. It is not resolvable with plain HTTP today.

This provider attempts the request and raises a clear, actionable error
so the orchestrator can fall through to the next provider. It is the
last stop in the chain.
"""

from __future__ import annotations

from ..models import MediaType, StreamInfo
from ..utils import ProviderError
from .base import BaseProvider

MULTIEMBED_BASE = "https://multiembed.mov"


class MultiEmbedError(ProviderError):
    pass


class MultiEmbedProvider(BaseProvider):
    name = "multiembed"
    priority = 30

    @property
    def _supported(self) -> bool:
        # Placeholder for a future Playwright-based implementation.
        return False

    def resolve(
        self,
        imdb_id: str,
        media_type: MediaType,
        season: int | None = None,
        episode: int | None = None,
    ) -> StreamInfo:
        raise MultiEmbedError(
            "multiembed uses Cloudflare Turnstile + obfuscated JS and cannot be "
            "resolved with plain HTTP. Install Playwright and a browser to enable "
            "this provider."
        )
