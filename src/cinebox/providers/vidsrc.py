"""Fallback provider: vidsrc.to / vsembed chain.

Chain:
  vidsrc.to/embed/{type}/{id}[/{season}/{episode}]
    → iframe → vsembed.ru/embed/{type}/{id}
      → /vs_src.php?type={type}&id={id}  → {"src": cloudorchestranova.com/embed/...}
        → page with CFG.metaApi (data.vidsrcme.ru)
          → api.php?type=&imdb=&stream_urls  → may be plain array (passthrough)
            or a ChaCha20-encrypted string (WASM-protected; unsupported here)

This provider resolves the plain passthrough path. If the source is
protected (encrypted stream_urls), it raises a clear error so the
orchestrator can fall through to the next provider.
"""

from __future__ import annotations

import json
import re

from ..models import MediaType, StreamInfo
from ..utils import Log, ProviderError, new_http_client, retry
from .base import BaseProvider

VIDSRC_BASE = "https://vidsrc.to"
VSTEMBED_BASE = "https://vsembed.ru"
META_API = "https://data.vidsrcme.ru/api.php"


class VidSrcError(ProviderError):
    pass


class EncryptedStreamError(VidSrcError):
    """Raised when stream_urls is encrypted (WASM-protected)."""


def _fetch(host: str, url: str, referer: str, origin: str = "") -> str:
    headers = {"Referer": referer}
    if origin:
        headers["Origin"] = origin
    with new_http_client(headers=headers) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


def _vs_src(media_type: MediaType, imdb_id: str) -> str:
    """Fetch the cloudorchestranova embed URL from vsembed's src API."""
    url = f"{VSTEMBED_BASE}/vs_src.php?type={media_type.value}&id={imdb_id}"
    Log.debug(f"GET {url}")

    def _do() -> str:
        body = _fetch(
            VSTEMBED_BASE,
            url,
            referer=f"{VSTEMBED_BASE}/embed/{media_type.value}/{imdb_id}/",
            origin=VSTEMBED_BASE,
        )
        try:
            return json.loads(body)["src"]
        except (json.JSONDecodeError, KeyError) as e:
            raise VidSrcError(f"vs_src.php returned unexpected JSON for {imdb_id}: {e}")

    return retry(_do)


def _meta_api(
    media_type: MediaType, imdb_id: str, embed_host: str
) -> dict:
    """Call the vidsrcme metadata API. stream_urls may be array or encrypted."""
    url = f"{META_API}?type={media_type.value}&imdb={imdb_id}&stream_urls"
    headers = {"Referer": f"https://{embed_host}/"}

    def _do() -> dict:
        with new_http_client(headers=headers) as client:
            resp = client.get(url)
            if resp.status_code == 404:
                raise VidSrcError(f"vidsrcme API 404 for {imdb_id}.")
            resp.raise_for_status()
        return resp.json()

    return retry(_do)


class VidSrcProvider(BaseProvider):
    name = "vidsrc"
    priority = 20

    def resolve(
        self,
        imdb_id: str,
        media_type: MediaType,
        season: int | None = None,
        episode: int | None = None,
    ) -> StreamInfo:
        src = _vs_src(media_type, imdb_id)
        parsed = re.match(r"https://([^/]+)/embed/", src)
        if not parsed:
            raise VidSrcError(f"Unexpected embed URL: {src[:80]}")
        embed_host = parsed.group(1)

        data = _meta_api(media_type, imdb_id, embed_host) or {}
        payload = data.get("data") or {}
        stream_urls = payload.get("stream_urls")

        if isinstance(stream_urls, list) and stream_urls:
            url = stream_urls[0]
            return StreamInfo(
                url=url,
                provider=self.name,
                headers={
                    "Referer": src,
                    "Origin": f"https://{embed_host}",
                },
                referer=src,
                title=payload.get("title") or imdb_id,
            )

        if isinstance(stream_urls, str):
            raise EncryptedStreamError(
                "vidsrc stream_urls are ChaCha20/WASM-protected; "
                "decryption not supported in cinebox yet."
            )

        raise VidSrcError("vidsrc API returned no usable stream URLs.")
