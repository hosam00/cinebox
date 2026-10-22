"""Subtitle handling.

Sources (three keyless, one optional account):

1. Provider-supplied tracks (imdb.su/vaplayer ``default_subs``), the same
   tracks the player's own subtitle chooser exposes. Empty for many titles.
2. YIFYS subtitles (yifysubtitles.ch) — anonymous movie page by IMDb ID,
   real .srt downloads (zip) for the configured languages.
3. SubSource (subsource.net) — anonymous TV-show season / movie pages
   with per-episode subtitle zips (whole-season packs are rejected because
   they can contain the wrong episode), grep-able from the server-rendered
   Next.js data payload (no API key, no captcha).
4. OpenSubtitles (api.opensubtitles.com) — best index for per-episode
   TV subs. Needs a free API key plus account username/password under
   ``[opensubtitles]``; queries by IMDb ID + season/episode, downloads
   via its REST download endpoint. Used as a last-resort source.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import time
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from .config import cache_dir, get
from .models import SubtitleTrack
from .utils import Log, new_http_client, validate_stream_url

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "*/*",
}

_YIFY_BASE = "https://yifysubtitles.ch"

# 2-letter config code -> YIFYS language label.
YIFY_LANGS = {
    "ar": "Arabic",
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "hi": "Hindi",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "zh": "Chinese",
    "it": "Italian",
    "tr": "Turkish",
    "nl": "Dutch",
    "pl": "Polish",
    "sv": "Swedish",
    "da": "Danish",
    "fi": "Finnish",
    "no": "Norwegian",
    "el": "Greek",
    "he": "Hebrew",
    "ko": "Korean",
    "id": "Indonesian",
    "ms": "Malay",
    "th": "Thai",
    "vi": "Vietnamese",
    "uk": "Ukrainian",
    "ro": "Romanian",
    "cs": "Czech",
    "hu": "Hungarian",
    "bg": "Bulgarian",
    "fa": "Persian",
    "sr": "Serbian",
    "hr": "Croatian",
}

# Human-readable language names shown in the subtitle picker.
LANG_NAMES = {
    "en": "English",
    "ar": "العربية",
    "fr": "Français",
    "es": "Español",
    "de": "Deutsch",
    "hi": "हिन्दी",
    "pt": "Português",
    "ru": "Русский",
    "ja": "日本語",
    "zh": "中文",
    "it": "Italiano",
    "tr": "Türkçe",
    "nl": "Nederlands",
    "pl": "Polski",
    "sv": "Svenska",
    "da": "Dansk",
    "fi": "Suomi",
    "no": "Norsk",
    "el": "Ελληνικά",
    "he": "עברית",
    "ko": "한국어",
    "id": "Bahasa Indonesia",
    "ms": "Bahasa Melayu",
    "th": "ไทย",
    "vi": "Tiếng Việt",
    "uk": "Українська",
    "ro": "Română",
    "cs": "Čeština",
    "hu": "Magyar",
    "bg": "Български",
    "fa": "فارسی",
    "sr": "Srpski",
}


def pick_track(tracks: list[SubtitleTrack], language: str) -> SubtitleTrack | None:
    """Pick the subtitle track closest to the requested language.

    Matches on the ISO code first, then by substring in the language label;
    falls back to the first track when nothing matches.
    """
    if not tracks:
        return None
    lang = (language or "").strip().lower()
    if not lang:
        return tracks[0]
    for t in tracks:
        if t.code.strip().lower() == lang:
            return t
    for t in tracks:
        label = t.lang.lower()
        if lang in label or label.startswith(lang):
            return t
    return tracks[0]


_YIFY_TO_CODE = {v.lower(): k for k, v in YIFY_LANGS.items()}


def _code_for_name(name: str) -> str:
    """Map a YIFYS language label (e.g. 'Arabic') back to a short code."""
    label = name.strip().lower()
    if label.startswith("chinese"):
        return "zh"
    if label.startswith("portuguese"):
        return "pt"
    return _YIFY_TO_CODE.get(label, label)


_SUBSOURCE_BASE = "https://subsource.net"
_SUBSOURCE_API = "https://api.subsource.net"

# SubSource catalog language slug -> 2-letter code.
SUBSOURCE_LANGS = {
    "english": "en",
    "arabic": "ar",
    "french": "fr",
    "spanish": "es",
    "german": "de",
    "hindi": "hi",
    "portuguese": "pt",
    "brazilian_portuguese": "pt",
    "russian": "ru",
    "japanese": "ja",
    "chinese": "zh",
    "big_5_code": "zh",
    "italian": "it",
    "turkish": "tr",
    "dutch": "nl",
    "polish": "pl",
    "swedish": "sv",
    "danish": "da",
    "finnish": "fi",
    "norwegian": "no",
    "greek": "el",
    "hebrew": "he",
    "korean": "ko",
    "indonesian": "id",
    "malay": "ms",
    "thai": "th",
    "vietnamese": "vi",
    "ukrainian": "uk",
    "romanian": "ro",
    "czech": "cs",
    "hungarian": "hu",
    "bulgarian": "bg",
    "persian": "fa",
    "farsi_persian": "fa",
    "serbian": "sr",
    "croatian": "hr",
    "bengali": "bn",
    "malayalam": "ml",
    "tamil": "ta",
    "telugu": "te",
    "urdu": "ur",
    "kurdish": "ku",
    "slovak": "sk",
    "slovenian": "sl",
    "estonian": "et",
    "latvian": "lv",
    "lithuanian": "lt",
    "icelandic": "is",
    "albanian": "sq",
    "armenian": "hy",
    "georgian": "ka",
    "macedonian": "mk",
    "bosnian": "bs",
    "afrikaans": "af",
    "mongolian": "mn",
    "nepali": "ne",
    "punjabi": "pa",
    "sinhala": "si",
    "swahili": "sw",
    "tagalog": "tl",
    "catalan": "ca",
    "galician": "gl",
    "basque": "eu",
    "welsh": "cy",
    "burmese": "my",
    "khmer": "km",
    "lao": "lo",
    "uzbek": "uz",
}


def _subsource_code(name: str) -> str:
    """Map a SubSource language slug (e.g. 'farsi_persian') to a short code."""
    label = (name or "").strip().lower().replace("-", "_")
    iso = SUBSOURCE_LANGS.get(label)
    if iso:
        return iso
    return _code_for_name(label.replace("_", " "))


def _subsource_slug(title: str) -> str:
    """Derive a SubSource URL slug from a show/movie title."""
    return re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")


_SUBSOURCE_REC_BEGIN = '{"id":'
_SUBSOURCE_EP_RE = re.compile(r"[Ss](\d{1,2})[eExX](\d{1,2})")


_ROW_RE = re.compile(r'<tr data-id="(\d+)">(.*?)</tr>', re.S)
_RATING_RE = re.compile(r'class="label[^"]*"[^>]*>\s*(\d+)\s*</span>')
_LANG_RE = re.compile(r'class="sub-lang">\s*([^<]+?)\s*</span>')
_SLUG_RE = re.compile(r'href="(/subtitles/[^"]+)"')
_RELEASES_RE = re.compile(r'<a href="/subtitles/[^"]+">(.*?)</a>', re.S)


def _parse_yify_movie(html: str, lang_codes: list[str]) -> list[SubtitleTrack]:
    """Extract subtitle tracks of the requested languages from a YIFYS page."""
    wanted = {c.strip().lower() for c in lang_codes if c.strip()}
    rows: list[tuple[int, SubtitleTrack]] = []
    seen: set[str] = set()
    for row_id, block in _ROW_RE.findall(html):
        slug_m = _SLUG_RE.search(block)
        if not slug_m:
            continue
        slug = slug_m.group(1)
        if slug in seen:
            continue
        seen.add(slug)
        lang_m = _LANG_RE.search(block)
        name = (lang_m.group(1).strip() if lang_m else "") or ""
        short = _code_for_name(name)
        if wanted and short not in wanted:
            continue
        display = LANG_NAMES.get(short, name)
        rating_m = _RATING_RE.search(block)
        try:
            rating = int(rating_m.group(1)) if rating_m else 0
        except ValueError:
            rating = 0
        labels = []
        releases = _RELEASES_RE.search(block)
        if releases:
            labels = [
                re.sub(r"<[^>]+>", "", part).strip() for part in releases.group(1).split("<br")
            ]
        release = next((x for x in labels if x), "") or slug.rsplit("/", 1)[-1]
        rows.append(
            (
                rating,
                SubtitleTrack(
                    lang=f"{display} — {release}",
                    code=short,
                    url=f"{_YIFY_BASE}/subtitle/{slug.rsplit('/', 1)[-1]}.zip",
                ),
            )
        )
    rows.sort(key=lambda t: t[0], reverse=True)
    return [t for _, t in rows]


def _cache_file(imdb_id: str, lang_codes: list[str]) -> Path:
    key = hashlib.md5(f"{imdb_id}|{','.join(sorted(lang_codes))}".encode()).hexdigest()
    return cache_dir() / f"yify_{key}.json"


def _cache_valid(path: Path) -> bool:
    try:
        ttl_hours = int(get("cache", "ttl_hours", 24))
    except (TypeError, ValueError):
        ttl_hours = 24
    if not path.exists():
        return False
    cutoff = time.time() - ttl_hours * 3600
    return path.stat().st_mtime > cutoff


def fetch_yify(
    imdb_id: str, langs: str | list[str] = "en", per_lang: int = 3
) -> list[SubtitleTrack]:
    """Search YIFYS subtitles by IMDb ID across one or more languages.

    ``langs`` may be a single code string or a list of short codes (e.g.
    ``"ar"``, ``"en"``). For each language the highest-rated subtitles are
    returned (up to ``per_lang`` each), labeled with the language name so the
    picker can group them. Results are cached on disk honoring ``[cache]
    ttl_hours``.
    """
    if isinstance(langs, str):
        langs = [langs]
    lang_codes = [c.strip().lower() for c in langs if c and c.strip()]
    if not lang_codes:
        return []

    cache_enabled = get("cache", "enabled", True)
    cache_path = _cache_file(imdb_id, lang_codes)
    if cache_enabled:
        try:
            if _cache_valid(cache_path):
                raw = json.loads(cache_path.read_text())
                return [track for entry in raw if (track := _track_from_cache(entry)) is not None]
        except (OSError, json.JSONDecodeError):
            pass

    tracks: list[SubtitleTrack] = []
    try:
        with new_http_client(headers=HEADERS) as client:
            resp = client.get(f"{_YIFY_BASE}/movie-imdb/{imdb_id}")
            resp.raise_for_status()
        tracks = _parse_yify_movie(resp.text, lang_codes)
    except Exception as e:  # noqa: BLE001 - subtitles are optional
        Log.debug(f"YIFYS subtitle fetch failed ({imdb_id}): {e}")

    if not tracks:
        return []

    capped = _cap_lang(tracks, per_lang)

    if cache_enabled:
        try:
            cache_path.write_text(json.dumps([t.model_dump() for t in capped]))
        except OSError:
            pass
    return capped


def _cap_lang(tracks: list[SubtitleTrack], per_lang: int) -> list[SubtitleTrack]:
    """Keep at most ``per_lang`` tracks per language, preserving order."""
    capped: list[SubtitleTrack] = []
    counts: dict[str, int] = {}
    for t in tracks:
        n = counts.get(t.code, 0)
        if n >= max(1, per_lang):
            continue
        counts[t.code] = n + 1
        capped.append(t)
    return capped


def _track_from_cache(entry: dict) -> SubtitleTrack | None:
    try:
        return SubtitleTrack(**entry)
    except (TypeError, ValueError, KeyError):
        return None


# -- SubSource (subsource.net) ---------------------------------------------


def _subsource_cache_file(
    slug: str,
    season: int | None,
    episode: int | None,
    lang_codes: list[str],
    year: int | None = None,
) -> Path:
    # Version the key so old season-pack caches are ignored; include ``year``
    # because movie remakes share a slug but not subtitles.
    key = hashlib.md5(
        f"v3|{slug}|{season or 'mo'}|{episode or 'x'}|{year or ''}|"
        f"{','.join(sorted(lang_codes))}".encode()
    ).hexdigest()
    return cache_dir() / f"subsource_{key}.json"


def _subsource_blob(html: str) -> str:
    """Unescape the Next.js ``self.__next_f`` payload the catalog is in."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.S)
    return "".join(
        chunk.encode().decode("unicode_escape", errors="replace").replace('\\"""', "")
        for chunk in chunks
    )


def _parse_subsource_page(
    html: str,
    page_slug: str,
    season: int | None,
    episode: int | None,
    lang_codes: list[str],
) -> list[SubtitleTrack]:
    """Extract subtitle tracks of the requested languages from a SubSource page.

    ``page_slug`` is the catalog link prefix (``{slug}-season-{N}`` for TV or
    ``{slug}-{year}`` for movies), which every record's ``link`` starts with.

    Each catalog record in the SSR payload looks like
    ``{"id":454247,"language":"arabic","release_type":"other",
    "release_info":"Breaking.Bad.S03E07.720p.HDTV.X264-DIMENSION",
    ...,"link":"breaking-bad-season-3/arabic/454247",...}``.
    """
    wanted = {c.strip().lower() for c in lang_codes if c.strip()}
    prefix = page_slug

    tracks: dict[tuple[str, str], SubtitleTrack] = {}
    order: list[tuple[str, str]] = []
    for part in _subsource_blob(html).split(_SUBSOURCE_REC_BEGIN)[1:]:
        link_m = re.search(r'"link":"((?:[^"\\]|\\.)*?)"', part)
        if not link_m:
            continue
        link = link_m.group(1).replace("\\/", "/")
        if not link.startswith(prefix + "/"):
            continue
        lang_m = re.search(r'"language":"([^"]+)"', part)
        release_m = re.search(r'"release_info":"([^"]*)"', part)
        release = (release_m.group(1) if release_m else "").strip()
        code = _subsource_code(lang_m.group(1) if lang_m else "")
        if wanted and code not in wanted:
            continue
        if episode is not None:
            ep_m = _SUBSOURCE_EP_RE.search(release)
            # Reject whole-season packs: selecting one file from the archive
            # can serve the wrong episode. Require an explicit SxxExx match.
            if not ep_m or int(ep_m.group(1)) != season or int(ep_m.group(2)) != episode:
                continue

        key = (code, release)
        if key in tracks:
            continue
        short = release or link.rsplit("/", 1)[-1]
        label = f"{LANG_NAMES.get(code, code or 'subtitles')} — {short}"
        tracks[key] = SubtitleTrack(
            lang=label,
            code=code,
            url=f"{_SUBSOURCE_BASE}/subtitle/{link}",
        )
        order.append(key)
    return [tracks[k] for k in order]


def fetch_subsource(
    title: str,
    langs: str | list[str] = "en",
    season: int | None = None,
    episode: int | None = None,
    year: int | None = None,
    per_lang: int = 3,
) -> list[SubtitleTrack]:
    """Search SubSource subtitles by title (and season/episode or year).

    Anonymous, no API key. TV shows are cataloged per season
    (``/subtitles/{slug}/season-{N}``), movies per ``/subtitles/{slug}-{year}``.
    Episodes are matched by the ``SxxExx`` release markers inside the catalog.
    Results are cached on disk honoring ``[cache] ttl_hours``.
    """
    if isinstance(langs, str):
        langs = [langs]
    lang_codes = [c.strip().lower() for c in langs if c and c.strip()]
    slug = _subsource_slug(title)
    if not lang_codes or not slug:
        return []

    cache_enabled = get("cache", "enabled", True)
    cache_path = _subsource_cache_file(slug, season, episode, lang_codes, year)
    if cache_enabled:
        try:
            if _cache_valid(cache_path):
                raw = json.loads(cache_path.read_text())
                return [track for entry in raw if (track := _track_from_cache(entry)) is not None]
        except (OSError, json.JSONDecodeError):
            pass

    tracks: list[SubtitleTrack] = []
    candidates = [slug]
    stripped = slug[4:] if slug.startswith("the-") else ""
    if stripped and stripped not in candidates:
        candidates.append(stripped)
    for cand in candidates:
        if season is not None:
            url = f"{_SUBSOURCE_BASE}/subtitles/{cand}/season-{season}"
            page_slug = f"{cand}-season-{season}"
        else:
            page_slug = f"{cand}-{year}" if year else cand
            url = f"{_SUBSOURCE_BASE}/subtitles/{page_slug}"
        try:
            with new_http_client(headers=HEADERS) as client:
                resp = client.get(url)
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                tracks = _parse_subsource_page(resp.text, page_slug, season, episode, lang_codes)
                break
        except Exception as e:  # noqa: BLE001 - subtitles are optional
            Log.debug(f"SubSource fetch failed ({page_slug}): {e}")
            break

    capped = _cap_lang(tracks, per_lang)
    if capped and cache_enabled:
        try:
            cache_path.write_text(json.dumps([t.model_dump() for t in capped]))
        except OSError:
            pass
    return capped


def download_subtitle(track: SubtitleTrack | dict, dest: str | Path) -> Path | None:
    """Download a subtitle track/entry to *dest* and return its path.

    Accepts a ``SubtitleTrack`` or a dict with a ``url`` (provider or YIFYS
    track). YIFYS URLs end in ``.zip``; the archive is unpacked and the
    subtitle file inside is saved.
    """
    if isinstance(track, dict):
        built = SubtitleTrack.from_api(track)
        if built is None:
            return None
        track = built
    return _download_url(track, dest)


_SUB_EXTS = (".srt", ".vtt", ".ass", ".ssa")


_NON_UTF8_CODECS = (
    "cp1256",  # Arabic
    "cp1251",  # Cyrillic
    "cp1253",  # Greek
    "cp1255",  # Hebrew
    "cp1254",  # Turkish
    "cp1258",  # Vietnamese
    "shift_jis",  # Japanese
    "gb18030",  # Chinese
    "cp949",  # Korean
    "cp874",  # Thai
    "cp1252",  # Western / any other single-byte
)

# Track language code (2-letter) -> preferred codepage when UTF-8 is absent.
_LANG_CODEC = {
    "ar": "cp1256",
    "el": "cp1253",
    "he": "cp1255",
    "tr": "cp1254",
    "vi": "cp1258",
    "ja": "shift_jis",
    "zh": "gb18030",
    "ko": "cp949",
    "th": "cp874",
    "ru": "cp1251",
    "uk": "cp1251",
    "bg": "cp1251",
    "sr": "cp1251",
    "be": "cp1251",
}

_SCRIPT_BLOCKS = {
    "cp1256": (0x0600, 0x06FF),  # Arabic
    "cp1251": (0x0400, 0x04FF),  # Cyrillic
    "cp1253": (0x0370, 0x03FF),  # Greek
    "cp1255": (0x0590, 0x05FF),  # Hebrew
    "shift_jis": (0x3040, 0x9FFF),  # Japanese / CJK
    "gb18030": (0x4E00, 0x9FFF),  # CJK ideographs
    "cp949": (0xAC00, 0xD7FF),  # Hangul
    "cp874": (0x0E00, 0x0E7F),  # Thai
    "cp1252": (0x00C0, 0x017F),  # Latin extended
}


def _candidate_codecs(code: str) -> list[str]:
    """Codepages to try for *code*, preferred first."""
    preferred = _LANG_CODEC.get((code or "").strip().lower())
    candidates = []
    for enc in _NON_UTF8_CODECS:
        if enc == preferred or enc in candidates:
            continue
        candidates.append(enc)
    if preferred:
        candidates.insert(0, preferred)
    return candidates


def _normalize_subtitle(data: bytes, code: str = "en") -> bytes:
    """Return subtitle *data* re-encoded as UTF-8 when possible.

    Old Arabic/European subtitle files ship in legacy codepages (Windows-1256
    is common for Arabic); a plain UTF-8 decode then fails and the player
    shows mojibake.  The track's language code biases the codepage choice so
    the right script wins over unrelated ones that also decode byte-for-byte.
    """
    try:
        data.decode("utf-8")
        return data
    except UnicodeDecodeError:
        pass
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16").encode("utf-8")

    for enc in _candidate_codecs(code):
        try:
            text = data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        lo, hi = _SCRIPT_BLOCKS.get(enc, _SCRIPT_BLOCKS["cp1252"])
        if sum(1 for ch in text if lo <= ord(ch) <= hi) >= 10:
            return text.encode("utf-8")
    # No codepage produced real script text; keep the bytes untouched.
    return data


def _decode_subtitle(data: bytes, code: str = "en") -> bytes | None:
    """Turn downloaded bytes into subtitle bytes, or ``None`` if unusable.

    Handles gzip wrappers and any-content zip archives (YIFYS delivers zips),
    and rejects HTML error pages.
    """
    if data[:2] == b"\x1f\x8b":
        import gzip

        try:
            data = gzip.decompress(data)
        except OSError:
            return None
    if data[:4] == b"PK\x03\x04":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                subs = [
                    (n, zf.read(n)) for n in zf.namelist() if Path(n).suffix.lower() in _SUB_EXTS
                ]
            if not subs:
                return None
            subs.sort(key=lambda s: len(s[1]), reverse=True)
            data = subs[0][1]
        except (zipfile.BadZipFile, OSError):
            return None
    if b"<html" in data[:256].lower():
        return None
    data = _normalize_subtitle(data, code)
    if b"-->" not in data and not (
        b"[script info]" in data[:512].lower() or b"dialogue:" in data[:512].lower()
    ):
        return None
    return data


def _safe_subtitle_code(code: str) -> str:
    """Return a filesystem-safe subtitle language code."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "", code or "")[:16]
    return cleaned.strip("._-") or "en"


def _subtitle_extension(data: bytes, fallback: str = ".srt") -> str:
    """Detect the subtitle container from its content."""
    head = data[:512].lower()
    if b"[script info]" in head or b"dialogue:" in head:
        return ".ass"
    return fallback if fallback in _SUB_EXTS else ".srt"


def _write_subtitle(data: bytes, path: Path) -> Path:
    """Write subtitle bytes, correcting the extension when content differs."""
    ext = _subtitle_extension(data, path.suffix.lower())
    if ext != path.suffix.lower():
        path = path.with_suffix(ext)
    path.write_bytes(data)
    return path


def _download_url(track: SubtitleTrack, dest: str | Path) -> Path | None:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    try:
        dest.chmod(0o700)
    except OSError:
        pass

    ext = Path(urlparse(track.url).path).suffix.lower()
    if ext not in _SUB_EXTS:
        ext = ".srt"
    path = dest / f"{_safe_subtitle_code(track.code)}{ext}"

    headers = dict(HEADERS)
    if track.url.startswith("os:"):
        return _download_opensubtitles(track.url[3:], path, headers, track.code)
    if "yifysubtitles.ch" in track.url:
        # YIFYS requires a referer from the subtitle detail page.
        slug = Path(urlparse(track.url).path).stem
        headers["Referer"] = f"{_YIFY_BASE}/subtitles/{slug}"
    if _SUBSOURCE_BASE in track.url:
        return _download_subsource(track, path, headers)

    try:
        with new_http_client(headers=headers) as client:
            resp = client.get(track.url)
            resp.raise_for_status()
        data = _decode_subtitle(resp.content, track.code or "en")
        if data is None:
            Log.debug(f"Subtitle download unusable ({track.code}): {track.url}")
            return None
        path = _write_subtitle(data, path)
    except Exception as e:  # noqa: BLE001 - optional feature
        Log.debug(f"Subtitle download failed ({track.code}): {e}")
        return None
    Log.info(f"Subtitle saved: {path}")
    return path


def _download_subsource(track: SubtitleTrack, path: Path, headers: dict[str, str]) -> Path | None:
    """Download a SubSource subtitle: detail page -> download hash -> zip.

    The catalog only stores the detail-page URL; the actual file alias lives
    on that page (``api.subsource.net/v1/subtitle/download/{hash}``).
    """
    try:
        with new_http_client(headers={**headers, "Referer": track.url}) as client:
            detail = client.get(track.url)
            detail.raise_for_status()
            link_m = re.search(
                r"(?:https://api\.subsource\.net)?/v1/subtitle/download/"
                r"([0-9a-f]{40,})",
                detail.text,
            )
            if not link_m:
                Log.debug(f"SubSource page has no download link: {track.url}")
                return None
            api_url = f"{_SUBSOURCE_API}/v1/subtitle/download/{link_m.group(1)}"
            resp = client.get(api_url, headers={"Referer": track.url})
            resp.raise_for_status()
        data = _decode_subtitle(resp.content, track.code or "en")
        if data is None:
            Log.debug(f"Subtitle download unusable ({track.code}): {track.url}")
            return None
        path = _write_subtitle(data, path)
    except Exception as e:  # noqa: BLE001 - optional feature
        Log.debug(f"Subtitle download failed ({track.code}): {e}")
        return None
    Log.info(f"Subtitle saved: {path}")
    return path


# -- OpenSubtitles (api.opensubtitles.com) ----------------------------------


_OS_BASE = "https://api.opensubtitles.com/api/v1"
_OS_TOKEN_TTL = 12 * 3600  # JWT lasts ~24h; refresh well before expiry.


def _os_api_key() -> str:
    if not get("opensubtitles", "enabled", True):
        return ""
    return get("opensubtitles", "api_key", "").strip()


def _os_credentials_fingerprint() -> str:
    """Hash the current OpenSubtitles credentials for token cache validation."""
    raw = "\0".join(
        (
            _os_api_key(),
            (get("opensubtitles", "username", "") or "").strip(),
            get("opensubtitles", "password", "") or "",
        )
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _os_token(refresh: bool = False) -> str | None:
    """Return a cached OpenSubtitles JWT, logging in (once) when needed."""
    if not _os_api_key():
        return None
    fingerprint = _os_credentials_fingerprint()
    cache_path = cache_dir() / "os_token.json"
    if not refresh:
        try:
            if cache_path.exists() and time.time() - cache_path.stat().st_mtime < _OS_TOKEN_TTL:
                cached = json.loads(cache_path.read_text())
                token = cached.get("token")
                if token and cached.get("fingerprint") == fingerprint:
                    cache_path.chmod(0o600)
                    return token
        except (OSError, json.JSONDecodeError):
            pass

    user = (get("opensubtitles", "username", "") or "").strip()
    pwd = get("opensubtitles", "password", "") or ""
    if not user or not pwd:
        Log.debug("OpenSubtitles login skipped: username/password not configured.")
        return None
    body = {"username": user, "password": pwd}
    try:
        with new_http_client(headers={**HEADERS, "Api-Key": _os_api_key()}) as client:
            resp = client.post(f"{_OS_BASE}/login", json=body)
            resp.raise_for_status()
            token = resp.json().get("token")
    except Exception as e:  # noqa: BLE001 - optional feature
        Log.debug(f"OpenSubtitles login failed: {e}")
        return None
    if not token:
        return None
    _os_remember_token(token, fingerprint)
    return token


def _os_remember_token(token: str, fingerprint: str | None = None) -> None:
    try:
        path = cache_dir() / "os_token.json"
        path.write_text(
            json.dumps(
                {
                    "token": token,
                    "fingerprint": fingerprint or _os_credentials_fingerprint(),
                }
            )
        )
        path.chmod(0o600)
    except OSError:
        pass


def _os_imdb_number(imdb_id: str) -> str | None:
    """Return the numeric IMDb ID for OpenSubtitles, or None if unsupported."""
    raw = (imdb_id or "").strip()
    if raw[:2].lower() == "tt":
        raw = raw[2:]
    if not raw.isdigit():
        return None
    return str(int(raw))


def _os_cache_file(
    imdb_id: str,
    season: int | None,
    episode: int | None,
    lang_codes: list[str],
) -> Path:
    key = hashlib.md5(
        f"os|{imdb_id}|{season or ''}|{episode or ''}|{','.join(sorted(lang_codes))}".encode()
    ).hexdigest()
    return cache_dir() / f"opensubs_{key}.json"


def _normalize_os_code(lang: str, wanted: set[str]) -> str | None:
    """Map an OpenSubtitles language tag (``pt-br``, ``en``) to a wanted code."""
    short = (lang or "").strip().lower().split("-")[0]
    return short if short in wanted else None


def _os_headers() -> dict[str, str]:
    headers = dict(HEADERS)
    headers["Api-Key"] = _os_api_key()
    token = _os_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_opensubtitles(
    imdb_id: str,
    langs: str | list[str] = "en",
    season: int | None = None,
    episode: int | None = None,
    per_lang: int = 3,
) -> list[SubtitleTrack]:
    """Search OpenSubtitles API v3 by IMDb ID (and season/episode for TV).

    Requires ``[opensubtitles] api_key`` plus account username/password.
    Tracks are labeled with the release name and downloaded later via the
    API ``/download`` endpoint. Results are cached on disk honoring
    ``[cache] ttl_hours``.
    """
    if isinstance(langs, str):
        langs = [langs]
    lang_codes = [c.strip().lower() for c in langs if c and c.strip()]
    imdb_number = _os_imdb_number(imdb_id)
    if not lang_codes or not _os_api_key() or imdb_number is None:
        return []

    cache_enabled = get("cache", "enabled", True)
    cache_path = _os_cache_file(imdb_id, season, episode, lang_codes)
    if cache_enabled:
        try:
            if _cache_valid(cache_path):
                raw = json.loads(cache_path.read_text())
                return [track for entry in raw if (track := _track_from_cache(entry)) is not None]
        except (OSError, json.JSONDecodeError):
            pass

    params = {
        # The API canonicalizes "tt0118480" -> "118480" via a 301; send the
        # bare numeric id to avoid the redirect.
        "imdb_id": imdb_number,
        "languages": ",".join(lang_codes),
        "ai_translated": "exclude",
        "order_by": "download_count",
        "order_direction": "desc",
        "per_page": "20",
    }
    if season is not None:
        params["season_number"] = str(season)
        params["episode_number"] = str(episode or 1)
    wanted = set(lang_codes)
    tracks: list[SubtitleTrack] = []
    try:
        with new_http_client(headers=_os_headers()) as client:
            resp = client.get(f"{_OS_BASE}/subtitles", params=params)
            if resp.status_code == 401:
                _os_token(refresh=True)
                with new_http_client(headers=_os_headers()) as retry_client:
                    resp = retry_client.get(f"{_OS_BASE}/subtitles", params=params)
            resp.raise_for_status()
            payload = resp.json()
        for item in payload.get("data", []):
            attr = item.get("attributes") or {}
            code = _normalize_os_code(attr.get("language"), wanted)
            if not code:
                continue
            files = attr.get("files") or []
            fid = next(
                (
                    f.get("file_id")
                    for f in files
                    if str(f.get("format", "")).lower() in ("srt", "vtt", "ass", "ssa")
                ),
                None,
            )
            if fid is None and files:
                fid = files[0].get("file_id")
            if fid is None:
                continue
            release = (
                (attr.get("release_name") or "") or (files[0].get("file_name") or "") or ""
            ).strip()
            if not release:
                release = f"episode {episode}" if episode else f"id {item.get('id')}"
            hi = " [HI]" if attr.get("hearing_impaired") else ""
            label = f"{LANG_NAMES.get(code, code)}{hi} — {release}"
            tracks.append(SubtitleTrack(lang=label, code=code, url=f"os:{fid}"))
    except Exception as e:  # noqa: BLE001 - subtitles are optional
        Log.debug(f"OpenSubtitles search failed ({imdb_id}): {e}")
        return []

    capped = _cap_lang(tracks, per_lang)
    if capped and cache_enabled:
        try:
            cache_path.write_text(json.dumps([t.model_dump() for t in capped]))
        except OSError:
            pass
    return capped


def _download_opensubtitles(
    file_id: str, path: Path, headers: dict[str, str], code: str = "en"
) -> Path | None:
    """Fetch an OpenSubtitles file: POST download token -> GET its byte link.

    Retries once on 401 (token refresh).
    """
    for attempt in range(2):
        token = _os_token(refresh=attempt > 0)
        if not token:
            return None
        bh = {
            **headers,
            "Api-Key": _os_api_key(),
            "Authorization": f"Bearer {token}",
        }
        try:
            with new_http_client(headers=bh) as client:
                r = client.post(f"{_OS_BASE}/download", json={"file_id": int(file_id)})
                if r.status_code == 401:
                    continue
                r.raise_for_status()
                link = (r.json() or {}).get("link")
                if not link:
                    Log.debug(f"OpenSubtitles download miss ({file_id})")
                    return None
            # Never send the API key/JWT to the arbitrary download host.
            link_url = validate_stream_url(link)
            with new_http_client(headers=HEADERS) as download_client:
                data = download_client.get(link_url)
                data.raise_for_status()
                content = data.content
        except Exception as e:  # noqa: BLE001 - optional feature
            status = getattr(getattr(e, "response", None), "status_code", None)
            detail = f"HTTP {status}" if status else type(e).__name__
            Log.debug(f"OpenSubtitles download failed ({file_id}): {detail}")
            return None
        decoded = _decode_subtitle(content, code or "en")
        if decoded is None:
            Log.debug(f"OpenSubtitles download unusable ({file_id})")
            return None
        path = _write_subtitle(decoded, path)
        Log.info(f"Subtitle saved: {path}")
        return path
    return None
