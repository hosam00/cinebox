"""Favorites persistence.

Users can save titles from the search results / action menus. A plain
JSON file under the config dir.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .config import cache_dir
from .models import MediaType, SearchResult

FAVORITES_FILE = "favorites.json"


class FavoritesManager:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or cache_dir() / FAVORITES_FILE

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text())
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, entries: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(entries, indent=2))

    def list(self) -> list[dict]:
        entries = self._load()
        entries.sort(key=lambda e: e.get("added_at", 0), reverse=True)
        return entries

    def add(self, result: SearchResult) -> None:
        entries = [e for e in self._load() if e.get("imdb_id") != result.imdb_id]
        entries.insert(0, {
            "imdb_id": result.imdb_id,
            "title": result.title,
            "year": result.year,
            "media_type": result.media_type.value,
            "cast": result.cast,
            "image_url": result.image_url,
            "added_at": time.time(),
        })
        self._save(entries)

    def has(self, imdb_id: str) -> bool:
        return any(e.get("imdb_id") == imdb_id for e in self._load())

    def remove(self, imdb_id: str) -> None:
        self._save([e for e in self._load() if e.get("imdb_id") != imdb_id])

    def to_search_result(self, entry: dict) -> SearchResult | None:
        """Rehydrate a stored dict into a SearchResult when possible."""
        try:
            return SearchResult(
                imdb_id=entry["imdb_id"],
                title=entry.get("title", ""),
                year=entry.get("year"),
                media_type=MediaType(entry.get("media_type", "movie")),
                cast=entry.get("cast", ""),
                image_url=entry.get("image_url", ""),
            )
        except (KeyError, ValueError):
            return None
