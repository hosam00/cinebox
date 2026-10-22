"""Pydantic data models for cinebox."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class MediaType(StrEnum):
    MOVIE = "movie"
    TV = "tv"


class SearchResult(BaseModel):
    """A single result from the IMDb suggestion endpoint."""

    imdb_id: str = Field(pattern=r"^tt\d+$|^[a-z0-9]+:[a-zA-Z0-9_-]+$")
    title: str
    year: int | None = None
    media_type: MediaType
    cast: str = ""
    image_url: str = ""

    @property
    def label(self) -> str:
        """fzf-friendly line format."""
        type_tag = "MOVIE" if self.media_type == MediaType.MOVIE else "TV"
        year = f" ({self.year})" if self.year else ""
        return f"[{type_tag}] {self.title}{year} — {self.imdb_id}"

    @classmethod
    def from_imdb_suggestion(cls, entry: object) -> SearchResult | None:
        """Parse a raw IMDb suggestion JSON entry into a SearchResult."""
        if not isinstance(entry, dict):
            return None
        media_type = _classify_media(entry)
        if media_type is None:
            return None

        imdb_id = entry.get("id")
        title = entry.get("l")
        if not isinstance(imdb_id, str) or not imdb_id.strip():
            return None
        if not isinstance(title, str) or not title.strip():
            return None

        year = entry.get("y") or entry.get("tl")
        try:
            year = int(year) if year else None
        except (TypeError, ValueError):
            year = None

        image = ""
        image_info = entry.get("i")
        if isinstance(image_info, dict):
            image = image_info.get("imageUrl")
            if not isinstance(image, str):
                image = ""

        cast = entry.get("s")
        if not isinstance(cast, str):
            cast = ""

        try:
            return cls(
                imdb_id=imdb_id.strip(),
                title=title.strip(),
                year=year,
                media_type=media_type,
                cast=cast,
                image_url=image,
            )
        except ValueError:
            return None


def _classify_media(entry: dict) -> MediaType | None:
    """Map IMDb suggestion q/qid fields to a MediaType, or None to skip."""
    q = entry.get("q") if isinstance(entry.get("q"), str) else ""
    qid = entry.get("qid") if isinstance(entry.get("qid"), str) else ""
    q = q.lower()
    qid = qid.lower()
    raw = f"{q} {qid}"

    movies = {"feature", "movie", "film", "short", "video"}
    tv = {"tv series", "tvseries", "tv", "series", "miniseries"}
    skip = {"tv episode", "video game", "podcast", "person", "title"}

    if any(k in raw for k in skip):
        return None
    if q in movies or qid in movies:
        return MediaType.MOVIE
    if q in tv or qid in tv:
        return MediaType.TV

    # Aliases found in the wild
    if "tv" in raw or "series" in raw:
        return MediaType.TV
    if "movie" in raw or "video" in raw:
        return MediaType.MOVIE
    return None


class SubtitleTrack(BaseModel):
    """A subtitle track offered by the provider or OpenSubtitles."""

    lang: str
    code: str = ""
    url: str = ""

    @classmethod
    def from_api(cls, entry: dict) -> SubtitleTrack | None:
        url = entry.get("url") or entry.get("link") or ""
        if not url:
            return None
        return cls(
            lang=entry.get("lang") or entry.get("label") or url,
            code=entry.get("code") or "",
            url=url,
        )

    @property
    def label(self) -> str:
        return self.lang or (self.code or "subtitles")


class StreamInfo(BaseModel):
    """A resolved playable stream."""

    url: str
    provider: str
    headers: dict[str, str] = Field(default_factory=dict)
    referer: str = ""
    title: str = ""
    quality_choices: list[str] = Field(default_factory=list)
    subtitles: list[SubtitleTrack] = Field(default_factory=list)

    def get_headers(self) -> dict[str, str]:
        """Build final headers, injecting referer when present."""
        headers = dict(self.headers)
        if self.referer and "Referer" not in headers:
            headers["Referer"] = self.referer
        return headers
