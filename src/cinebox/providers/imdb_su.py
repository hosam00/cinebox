"""Primary provider: imdb.su / vaplayer.ru stream API.

The resolution chain:
  1. imdb.su/embed/{type}/{id} redirects to player.imdb.su, whose page
     hosts an iframe to a rotating player domain (currently
     nextgencloudfabric.com).
  2. That player page calls:
       GET https://streamdata.vaplayer.ru/api.php?imdb={id}&type={type}[&s][&e]
     requiring Referer/Origin headers that point at the player domain.
  3. The API returns a JSON body with a stream_urls[] array of HLS URLs.

The API call works with plain HTTP + header spoofing; no Turnstile or
Playwright needed for this endpoint today.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from ..config import USER_AGENT
from ..models import MediaType, StreamInfo, SubtitleTrack
from ..utils import Log, ProviderError, new_http_client, retry
from .base import BaseProvider

SW_BASE = "https://imdb.su"
EMBED_HOST = "nextgencloudfabric.com"
STREAM_API = "https://streamdata.vaplayer.ru/api.php"


class ImdbSuError(ProviderError):
    pass


def _discover_player_host() -> str:
    """Follow the embed redirect and scrape the iframe src for the player host.

    Falls back to the known EMBED_HOST constant if discovery fails, so the
    provider stays resilient to dead domains.
    """
    try:
        with new_http_client(follow_redirects=True) as client:
            resp = client.get(f"{SW_BASE}/embed/movie/tt0000000")
            resp.raise_for_status()
        match = re.search(r'<iframe[^>]*src="([^"]+)"', resp.text)
        if match:
            host = urlparse(match.group(1)).hostname
            if host:
                Log.debug(f"Discovered player host: {host}")
                return host
    except Exception as e:  # noqa: BLE001 - non-fatal discovery
        Log.debug(f"Player host discovery failed: {e}")
    Log.debug(f"Using fallback player host: {EMBED_HOST}")
    return EMBED_HOST


def fetch_stream_api(
    imdb_id: str,
    media_type: MediaType,
    season: int | None = None,
    episode: int | None = None,
    host: str | None = None,
) -> dict:
    """Call the vaplayer stream API and return the parsed JSON body."""
    host = host or EMBED_HOST
    params: list[str] = [f"imdb={imdb_id}", f"type={media_type.value}"]
    if season is not None:
        params.append(f"s={season}")
    if episode is not None:
        params.append(f"e={episode}")
    query = "&".join(params)

    embed_path = f"/embed/{media_type.value}/{imdb_id}"
    if season is not None:
        embed_path += f"/{season}"
        if episode is not None:
            embed_path += f"/{episode}"
    embed_url = f"https://{host}{embed_path}"

    url = f"{STREAM_API}?{query}"
    Log.debug(f"GET {url}")
    Log.debug(f"Referer: {embed_url}")

    def _do() -> dict:
        with new_http_client(
            headers={"Referer": embed_url, "Origin": f"https://{host}"}
        ) as client:
            resp = client.get(url)
            if resp.status_code == 404:
                raise ImdbSuError(
                    f"Stream API returned 404 (imdb={imdb_id}). "
                    "Title may be unavailable."
                )
            resp.raise_for_status()
            data = resp.json()
        if data.get("status_code") not in ("200", 200):
            raise ImdbSuError(
                f"Stream API error: {data.get('status_code')} {data.get('error', '')}"
            )
        return data

    return retry(_do)


def _parse_quality_variants(master_url: str, host: str) -> list[dict]:
    """Fetch a master.m3u8 and extract the quality variant descriptions."""
    variants: list[dict] = []
    try:
        with new_http_client(
            timeout=5.0,
            headers={"Referer": f"https://{host}/embed/movie/", "Origin": f"https://{host}"}
        ) as client:
            resp = client.get(master_url)
            resp.raise_for_status()
            for line in resp.text.splitlines():
                if line.startswith("#EXT-X-STREAM-INF"):
                    band = re.search(r"BANDWIDTH=(\d+)", line)
                    res = re.search(r"RESOLUTION=(\d+x\d+)", line)
                    variants.append(
                        {
                            "bandwidth": int(band.group(1)) if band else 0,
                            "resolution": res.group(1) if res else "?",
                        }
                    )
    except Exception as e:  # noqa: BLE001
        Log.debug(f"Could not parse quality variants from {master_url}: {e}")
    return variants


class ImdbSuProvider(BaseProvider):
    name = "imdb_su"
    priority = 10

    def resolve(
        self,
        imdb_id: str,
        media_type: MediaType,
        season: int | None = None,
        episode: int | None = None,
    ) -> StreamInfo:
        host = _discover_player_host()
        data = fetch_stream_api(imdb_id, media_type, season, episode, host=host)

        info = data.get("data", {})
        stream_urls = info.get("stream_urls") or []
        if not stream_urls:
            raise ImdbSuError("API returned no stream URLs.")

        if not info.get("imdb_id"):
            info["imdb_id"] = imdb_id

        url = stream_urls[0]
        variants = _parse_quality_variants(url, host)
        quality_flags = [
            f"{v.get('resolution')} ({round(v.get('bandwidth', 0) / 1_000_000, 1)} Mbps)"
            for v in variants
        ]

        title = info.get("title") or imdb_id
        subtitles = [
            t
            for raw in (data.get("default_subs") or [])
            if (t := SubtitleTrack.from_api(raw)) is not None
        ]
        return StreamInfo(
            url=url,
            provider=self.name,
            headers={
                "User-Agent": USER_AGENT,
                "Referer": f"https://{host}/embed/{media_type.value}/{imdb_id}",
                "Origin": f"https://{host}",
            },
            referer=f"https://{host}/embed/{media_type.value}/{imdb_id}",
            title=title,
            quality_choices=quality_flags,
            subtitles=subtitles,
        )

    @staticmethod
    def episode_map(imdb_id: str, host: str | None = None) -> dict[str, list[str]]:
        """Return the {season: [episodes]} map from the API response."""
        data = fetch_stream_api(imdb_id, MediaType.TV, host=host)
        return data.get("data", {}).get("eps") or {}
