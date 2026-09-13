<div align="center">

# 🎬 cinebox

**A terminal-based movie streaming tool. Like ani-cli, but for cinema.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![tests](https://img.shields.io/badge/tests-126%20passing-brightgreen)]()
[![PyPI version](https://img.shields.io/pypi/v/cinebox?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/cinebox/)

</div>

<p align="center">
  <em>record with vhs / asciinema — replace <code>docs/demo.gif</code> with your recording</em>
</p>

<p align="center">
  <img src="docs/demo.gif" alt="cinebox demo — search, stream, and play in the terminal" width="700" />
</p>

A terminal-based tool to search, stream, and download movies and TV shows — inspired by [ani-cli](https://github.com/pystardust/ani-cli), built in Python with a rich interactive TUI and a provider-based streaming architecture.

Watch in **mpv** or **VLC**, download via **yt-dlp**, fetch **subtitles** — all without a single API key.

```
┌─────────┐   Rich TUI    ┌──────────┐    resolve    ┌──────────────┐   play    ┌───────┐
│  IMDb   │ ─────────────▶│ cinebox  │ ─────────────▶│   provider   │──────────▶│  mpv  │
│ suggest │               └──────────┘               │ (imdb_su ·   │          │  vlc  │
└─────────┘                    │                     │  vidsrc · …) │          └───────┘
                               └──▶ yt-dlp ───▶ .mp4/.mkv   (download)
```

## ✨ Features

- **No API keys, no accounts** — search runs against IMDb's public suggestion endpoint.
- **Rich TUI** — arrow-key navigation, themed panels, full-screen menus, ANSI poster art.
- **Stream or download** movies and TV episodes via a provider fallback chain.
- **Batch download** — mark multiple TV episodes and grab them all at once.
- **Subtitles** — anonymous fetching for movies and TV (Arabic + more via TUI settings).
- **History & Favorites** — relaunch titles from a watch list or save them for later.
- **Settings menu** — configure player, download paths, quality, theme, and subtitles from the TUI.
- **17 color themes** — blue, red, purple, sunset, mint, coral, and more.
- **Discord Rich Presence** — now-playing status (optional, needs a client ID).
- **Headless-friendly** — numbered menu fallback for piped/SSH sessions.
- **Open to extensions** — drop a new provider file into `providers/` and it registers itself automatically.

## 📦 Requirements

- Python 3.11+
- A media player: **mpv** (default) or **vlc**
- `yt-dlp` + `ffmpeg` on your `PATH` for downloads
- Optional: `pypresence` for Discord Rich Presence

## 🚀 Installation

### PyPI (recommended)

```bash
pipx install cinebox     # cleanest: isolated tool install
uv tool install cinebox  # same thing, uv-managed
pip install cinebox      # or plain pip
```

> **`pipx`** keeps cinebox and its dependencies in an isolated environment
> so they never clash with your other Python packages. Install `pipx` with
> `pipx --help` → `pipx install pipx` if you don't have it yet.

### Local checkout (development)

```bash
git clone https://github.com/hosam00/cinebox
cd cinebox
uv sync --group dev    # create .venv + install all deps
uv run cinebox --help  # verify
```

## 🎮 Quick start

### Interactive home screen (TUI)

```bash
cinebox
```

Type a query to search, or use the home keys below. Everything else is driven
by arrow keys, `Enter`, `D` for download, `S` for settings.

### Stream directly by IMDb ID

```bash
cinebox play tt0133093                      # The Matrix (1999)
cinebox play tt0944947 -t tv -s 1 -e 1      # GoT S01E01
```

### Download

```bash
cinebox download "the matrix" -q 720p
cinebox download "breaking bad" -t tv
```

### Headless search

```bash
echo 1 | cinebox search "inception" -t movie
```

## ⌨️ Key bindings

| Key       | Context        | Action                                   |
|-----------|----------------|------------------------------------------|
| `↑` / `↓` | All menus      | Navigate                                 |
| `Enter`   | Results        | Play selected                            |
| `Enter`   | Quality menu   | Watch                                    |
| `D`       | Quality menu   | Download at highlighted quality          |
| `D`       | Episode picker | Download marked (or highlighted)         |
| `Space`   | Episode picker | Toggle mark for batch download           |
| `F`       | Search results | Toggle favorite                          |
| `b`       | Any menu       | Back                                     |
| `q`       | Any menu       | Quit                                     |

## ⚙️ Configuration

First run creates `~/.config/cinebox/config.toml`. Notable options:

```toml
[player]
default = "mpv"        # mpv | vlc
fullscreen = true
extra_args = []        # extra args passed to the player (e.g. ["--mute"])

[download]
movies_dir = "~/Movies"
tv_dir = "~/Movies/TV"
quality = "1080p"
parallel_fragments = 3 # 1–16 concurrent download segments

[ui]
theme = "blue"         # one of 17 themes

[discord]
enabled = false        # requires a registered client ID
client_id = ""

[subtitle]
enabled = true
source = "auto"        # auto | provider | yifysubtitles | subsource
default_lang = "en"
languages = ["en", "ar"]
auto_download = false  # auto-fetch subs on watch (adds latency)
```

Any unset key falls back to its default. Everything above the `[discord]`
section is also editable from the TUI settings menu (`S`).

## 🔧 How it works

1. **Search** — `GET https://v3.sg.media-imdb.com/suggestion/{char}/{query}.json`
   returns matching titles with IMDb IDs. No auth. Keyword-based providers
   (e.g. Stardima) are merged automatically when present in the provider chain.
2. **Resolve** — providers turn an IMDb ID into a playable HLS/MP4 URL:
   - `imdb_su` (primary) — follows the embed player chain to the `vaplayer.ru`
     stream API; headers are spoofed so the CDN serves child manifests.
   - `vidsrc` (best-effort) — `vidsrc.to` → `vsembed.ru` → vidsrc data API.
     Encrypted results that need a browser are skipped.
   - `multiembed` (best-effort) — currently Turnstile-gated and skipped.
   Providers are **auto-discovered** when dropped into `src/cinebox/providers/`.
   Set `priority` on your class to control chain order (lower runs first).
3. **Play** — mpv/VLC receive the URL plus the required `Referer`/`Origin`/
   `User-Agent` headers, so the stream actually plays.
4. **Download** — the same resolved URL is handed to `yt-dlp` (optionally with
   subtitle muxing) and saved under your configured movies/TV directories.

Providers are tried in order; if one fails, the next takes over. Some providers
can vanish or change overnight — resolution is best-effort by design.

## 🗂️ Project layout

```
src/cinebox/
├── __init__.py          click CLI + TUI orchestration (search / play / download)
├── config.py            TOML config: defaults, paths, endpoints
├── search.py            IMDb suggestion endpoint + merged search_all()
├── models.py            pydantic models (SearchResult, StreamInfo, MediaType)
├── metadata.py          best-effort IMDb title-page enrichment (cached)
├── history.py           watch history persistence
├── favorites.py         favorites persistence
├── settings.py          interactive settings catalog + editor
├── discord_rpc.py       optional Discord Rich Presence
├── utils.py             logging, HTTP client, retry helpers
├── player.py            mpv / VLC launch command builders
├── downloader.py        yt-dlp wrapper + quality mapping
├── subtitles.py         anonymous subtitle fetch (movies + TV)
├── ui/
│   ├── themes.py        17 color themes
│   ├── art.py           ASCII header + goodbye art
│   ├── terminal.py      raw terminal I/O helpers
│   ├── components.py    menus, loading, episode picker, error panel, layout
│   └── poster.py        ANSI truecolor poster rendering (Pillow + numpy)
└── providers/
    ├── base.py          BaseProvider, ProviderRegistry, ResolutionError
    ├── discovery.py     auto-discovery of concrete providers
    ├── keyword.py       KeywordProvider ABC for keyword-search platforms
    ├── imdb_su.py       primary provider (vaplayer stream API)
    ├── vidsrc.py        best-effort fallback
    └── multiembed.py    best-effort fallback (Turnstile-gated)
```

## 🧪 Development

```bash
uv sync --group dev
uv run pytest            # 126 hermetic tests, no network
uv run ruff check src tests
```

To run the tool headlessly against the live network while developing:

```bash
env HOME=/tmp/fakehome uv run cinebox search "the matrix" -t movie
```

### Adding a new provider

Drop a Python file into `src/cinebox/providers/` (e.g. `stardima.py`):

```python
from __future__ import annotations
from cinebox.providers.base import BaseProvider
from cinebox.models import MediaType, StreamInfo

class StardiMaProvider(BaseProvider):
    name = "stardima"
    priority = 40          # lower number = runs first in the chain

    def resolve(self, imdb_id: str, media_type: MediaType,
                season: int | None = None, episode: int | None = None) -> StreamInfo:
        # ... fetch the stream URL from stardima ...
        ...
```

That's it — **no registry edits required**. `discovery.py` picks up any
concrete `BaseProvider` subclass in the package and adds it to the chain.
Set `priority` to control position (default `100`; `imdb_su` is `10`,
`vidsrc` `20`, `multiembed` `30`).

#### Keyword-search platforms (e.g. Stardima)

If your source resolves streams by raw keywords rather than IMDb IDs,
subclass `KeywordProvider` instead:

```python
from cinebox.providers.keyword import KeywordProvider
from cinebox.models import SearchResult

class StardiMaProvider(KeywordProvider):
    scheme = "stardima"
    priority = 40

    def search(self, query, media_type=None):
        # return list[SearchResult] — use self.synthetic_id("12345") for
        # IDs the platform can't map back to IMDb
        ...

    def resolve(self, imdb_id, media_type, season=None, episode=None):
        # imdb_id may be synthetic: "stardima:12345"
        ...
```

Keyword providers are merged into search results automatically alongside
IMDb suggestions. See `src/cinebox/providers/keyword.py` for the full interface.

## ✅ Roadmap

- [x] PyPI release via Trusted Publishing
- [x] Keyword-search provider interface (Stardima-ready)
- [x] Auto-discovery for drop-in providers
- [ ] `fzf` integration / fuzzy search over history & favorites
- [ ] More subtitle sources (incl. forced/embedded options)
- [ ] Provider config: per-provider enable/disable + health checks
- [ ] A full Stardima keyword provider (PR welcome)

## ⚠️ Disclaimer

For content you have the right to consume. The tool indexes publicly
accessible streams and hosts no media. Providers and their CDNs may change or
break at any time — use at your own risk, and always respect copyright.

Read the full [MIT license](LICENSE).

---

<p align="center">
  <sub>Made with ❤️· Rich · yt-dlp · Python</sub>
</p>