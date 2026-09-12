"""Best-effort metadata enrichment from the public IMDb title page.

IMDb serves the title page with embedded JSON-LD that includes rating,
genre, runtime, plot and directors. We scrape that key-free and cache the
result on disk under the cinebox cache directory. Any failure degrades
gracefully to an empty Metadata so the TUI never crashes.
"""

from __future__ import annotations

import functools
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import cache_dir
from .utils import Log, new_http_client

IMDB_TITLE_URL = "https://www.imdb.com/title/{imdb_id}/"


@dataclass
class Metadata:
    rating: list[float] | None = None
    genres: list[str] = field(default_factory=list)
    runtime: str = ""
    plot: str = ""
    directors: str = ""

    @property
    def is_empty(self) -> bool:
        return not (self.rating or self.genres or self.runtime or self.plot)

    def as_dict(self) -> dict:
        return asdict(self)


def _cache_file(imdb_id: str) -> Path:
    return cache_dir() / f"meta_{imdb_id}.json"


def _from_cache(imdb_id: str) -> Metadata | None:
    path = _cache_file(imdb_id)
    if not path.exists():
        return None
    try:
        return Metadata(**json.loads(path.read_text()))
    except (json.JSONDecodeError, TypeError, OSError):
        return None


def _to_cache(imdb_id: str, meta: Metadata) -> None:
    try:
        _cache_file(imdb_id).write_text(json.dumps(meta.as_dict()))
    except OSError:
        pass


def _parse_json_ld(page: str) -> dict | None:
    """Extract and decode the first application/ld+json block."""
    match = re.search(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _parse_iso_runtime(iso: str) -> str:
    """Convert 'PT2H19M' -> '2h 19m' (or pass through unknown formats)."""
    if not iso:
        return ""
    hours = re.match(r"PT(\d+)H", iso)
    mins = re.search(r"(\d+)M", iso)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours.group(1)}h")
    if mins:
        parts.append(f"{mins.group(1)}m")
    return " ".join(parts) if parts else iso


def fetch_metadata(imdb_id: str) -> Metadata:
    """Fetch (or load cached) metadata for an IMDb title."""
    cached = _from_cache(imdb_id)
    if cached is not None:
        return cached

    meta = Metadata()
    try:
        with new_http_client(timeout=8.0) as client:
            resp = client.get(IMDB_TITLE_URL.format(imdb_id=imdb_id))
            resp.raise_for_status()
        data = _parse_json_ld(resp.text)
        if data:
            meta.genres = [g for g in (data.get("genre") or []) if isinstance(g, str)]
            rating = data.get("aggregateRating") or {}
            if rating.get("ratingValue") is not None:
                try:
                    rating_count = float(rating.get("ratingCount", 0))
                    meta.rating = [float(rating["ratingValue"]), rating_count]
                except (TypeError, ValueError):
                    pass
            meta.runtime = _parse_iso_runtime(data.get("duration", ""))
            plot = data.get("description") or ""
            meta.plot = " ".join(plot.split())[:400]
            directors = data.get("director") or []
            names = [d.get("name") for d in directors if isinstance(d, dict) and d.get("name")]
            meta.directors = ", ".join(names)
    except Exception as e:  # noqa: BLE001 - non-fatal enrichment
        Log.debug(f"Metadata fetch failed for {imdb_id}: {e}")

    _to_cache(imdb_id, meta)
    return meta


@functools.lru_cache(maxsize=128)
def fetch_metadata_cached(imdb_id: str) -> Metadata:
    """Thread-safe cached wrapper used by the interactive results menu."""
    return fetch_metadata(imdb_id)
