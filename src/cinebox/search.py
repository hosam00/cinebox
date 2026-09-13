"""Search the IMDb suggestion endpoint for movies and TV shows.

Endpoint: GET https://v3.sg.media-imdb.com/suggestion/{first_char}/{query}.json
No API key required. Returns IMDb IDs directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from .models import MediaType, SearchResult
from .utils import Log, SearchError, new_http_client, retry

if TYPE_CHECKING:
    from .providers import ProviderRegistry

SUGGESTION_BASE = "https://v3.sg.media-imdb.com/suggestion"


def _suggestion_url(query: str) -> str:
    """Build the suggestion endpoint URL for a query."""
    q = query.strip().lower().replace(" ", "_")
    if not q:
        raise ValueError("query cannot be empty")
    return f"{SUGGESTION_BASE}/{q[0]}/{quote(q)}.json"


def _fetch_suggestions(query: str) -> list[dict]:
    url = _suggestion_url(query)
    Log.debug(f"GET {url}")

    def _do() -> list[dict]:
        with new_http_client() as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
        return data.get("d", [])

    return retry(_do)


def search(query: str, media_type: MediaType | None = None) -> list[SearchResult]:
    """Return matching SearchResult entries, filtered by optional media_type."""
    if not query.strip():
        raise SearchError("Empty search query.")

    raw = _fetch_suggestions(query)
    results: list[SearchResult] = []
    seen: set[str] = set()
    for entry in raw:
        result = SearchResult.from_imdb_suggestion(entry)
        if result is None:
            continue
        if media_type is not None and result.media_type != media_type:
            continue
        if result.imdb_id in seen:
            continue
        seen.add(result.imdb_id)
        results.append(result)
    return results


def search_movies(query: str) -> list[SearchResult]:
    return search(query, MediaType.MOVIE)


def search_tv(query: str) -> list[SearchResult]:
    return search(query, MediaType.TV)


def search_all(
    query: str,
    media_type: MediaType | None = None,
    registry: ProviderRegistry | None = None,
) -> list[SearchResult]:
    """Search IMDb suggestions, then any keyword-capable providers.

    Keyword results are appended after IMDb matches (deduplicated by
    ``imdb_id``) when a registry is supplied. A ``None`` registry keeps
    this a pure IMDb search for callers that do not need keyword sources.
    """
    results = search(query, media_type)
    if registry is None:
        return results
    seen = {r.imdb_id for r in results}
    for result in registry.search(query, media_type):
        if result.imdb_id in seen:
            continue
        seen.add(result.imdb_id)
        results.append(result)
    return results
