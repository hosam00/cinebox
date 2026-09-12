"""Watch history persistence (relaunch list).

Stores recently played or downloaded titles so the user can jump back
into them from the main menu. A plain JSON file under the config dir.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .config import cache_dir, get

HISTORY_FILE = "history.json"


class HistoryManager:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or cache_dir() / HISTORY_FILE

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

    def add(self, item: dict) -> None:
        """Record a watched/downloaded item (keyed by imdb_id + season/ep)."""
        if not get("history", "enabled", True):
            return
        key = (item.get("imdb_id"), item.get("season"), item.get("episode"))
        entries = [
            e for e in self._load()
            if (e.get("imdb_id"), e.get("season"), e.get("episode")) != key
        ]
        entry = dict(item)
        entry["last_watched"] = time.time()
        entries.insert(0, entry)
        max_entries = get("history", "max_entries", 50)
        self._save(entries[:max_entries])

    def list(self) -> list[dict]:
        entries = self._load()
        entries.sort(key=lambda e: e.get("last_watched", 0), reverse=True)
        return entries

    def clear(self) -> None:
        self._save([])

    def remove(self, imdb_id: str, season=None, episode=None) -> None:
        entries = [
            e for e in self._load()
            if not (
                e.get("imdb_id") == imdb_id
                and e.get("season") == season
                and e.get("episode") == episode
            )
        ]
        self._save(entries)
