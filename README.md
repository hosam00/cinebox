<div align="center">

# cinebox

**Search, stream, and download movies and TV shows from your terminal.**

[![CI](https://github.com/hosam00/cinebox/actions/workflows/ci.yml/badge.svg)](https://github.com/hosam00/cinebox/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/cinebox?logo=pypi&logoColor=white)](https://pypi.org/project/cinebox/)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/hosam00/cinebox/blob/main/LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

</div>

`cinebox` is a Python TUI for browsing IMDb, resolving playable streams through
a provider chain, and opening them in **mpv** or **VLC**. It supports TV episode
browsing, batch downloads, subtitles, history, favorites, and a configurable
terminal interface.

Inspired by [ani-cli](https://github.com/pystardust/ani-cli). `cinebox` indexes
publicly accessible sources and hosts no media.

## Features

- **Terminal-first interface** — arrow-key navigation, themed panels, ANSI
  poster art, and a numbered fallback for SSH or non-interactive sessions.
- **Movies and TV** — search IMDb, pick a season and episode, or jump directly
  to an IMDb ID.
- **Provider fallback chain** — if one source fails, the next provider is tried
  automatically.
- **Stream or download** — open a stream in mpv/VLC or save it locally with
  yt-dlp. TV episodes can be marked and downloaded in batches.
- **Subtitles** — keyless YIFY and SubSource sources, plus optional
  OpenSubtitles support for movies and per-episode TV subtitles.
- **History and favorites** — resume a recent title or keep a personal watch
  list.
- **Configurable** — player, download paths, quality, 17 color themes, poster
  scale, subtitle languages, and Discord Rich Presence.
- **Extensible** — drop a new provider into `src/cinebox/providers/` and it is
  discovered automatically.

## Requirements

- Python **3.11+**
- **mpv** (default) or **VLC**
- **yt-dlp** and **ffmpeg** on your `PATH` for downloads
- Linux is the primary target; macOS should work when the media tools are
  installed

Optional: `pypresence` for Discord Rich Presence.

## Installation

### Package manager

```bash
uv tool install cinebox
# or
pipx install cinebox
```

Run without installing:

```bash
uvx cinebox
```

### From source

```bash
git clone https://github.com/hosam00/cinebox
cd cinebox
uv sync --group dev
uv run cinebox
```

## Usage

```bash
# Interactive home screen
cinebox

# Search IMDb
cinebox search "the matrix" -t movie
cinebox search "breaking bad" -t tv

# Stream by IMDb ID
cinebox play tt0133093
cinebox play tt0944947 -t tv -s 1 -e 1

# Download
cinebox download "the matrix" -q 720p
cinebox download "breaking bad" -t tv
```

| Command | Description |
| --- | --- |
| `cinebox` | Open the interactive home screen |
| `cinebox search <query>` | Search IMDb and browse results |
| `cinebox play <imdb-id>` | Stream a movie or TV episode directly |
| `cinebox download <query>` | Search and download a title |

For scripted or headless use:

```bash
printf '1\n' | cinebox search "inception" -t movie
```

Use `cinebox -v` for debug logging.

## Key bindings

| Key | Context | Action |
| --- | --- | --- |
| `Up` / `Down` | All menus | Navigate |
| `Enter` | Results | Play selected |
| `Enter` | Quality menu | Watch |
| `d` | Quality menu | Download at highlighted quality |
| `d` | Episode picker | Download marked or highlighted episodes |
| `Space` | Episode picker | Toggle episode mark |
| `f` | Search results | Toggle favorite |
| `b` | Any menu | Back |
| `q` | Any menu | Quit |

## Configuration

The first run creates `~/.config/cinebox/config.toml`. Settings can also be
edited from the TUI with `S`.

```toml
[player]
default = "mpv"        # mpv | vlc
fullscreen = true
extra_args = []

[download]
movies_dir = "~/Movies"
tv_dir = "~/Movies/TV"
quality = "1080p"

[ui]
theme = "blue"         # one of 17 themes
poster_scale = 1.0

[subtitle]
enabled = true
source = "auto"        # auto | provider | yifysubtitles | subsource | opensubtitles
default_lang = "en"
auto_download = false

[opensubtitles]
enabled = true
api_key = ""           # app key from opensubtitles.com
username = ""
password = ""

[cache]
enabled = true
ttl_hours = 24
```

Unset keys fall back to their defaults. See
[`src/cinebox/config.py`](https://github.com/hosam00/cinebox/blob/main/src/cinebox/config.py) for the full configuration
surface, including history, Discord, download concurrency, and subtitle
languages.

### Security

If OpenSubtitles is configured, `config.toml` contains an API key and account
password in plaintext. The file is created with `0600` permissions and lives
outside the repository, but it should still be treated as a secret. Never
commit or share it. Rotate any credential that may have been exposed.

## How it works

```text
 IMDb suggestions
       │
       ▼
  ┌─────────┐    resolve     ┌─────────────────────────┐
  │ cinebox │ ─────────────▶ │ provider chain          │
  └─────────┘                │ imdb_su → vidsrc → ...  │
       │                     └────────────┬────────────┘
       │ download                         │ play
       ▼                                  ▼
    yt-dlp                            mpv / VLC
```

1. **Search** — queries IMDb's public suggestion endpoint and merges results
   from keyword-based providers when available.
2. **Resolve** — providers turn an IMDb ID into an HLS or MP4 stream URL and
   return the headers required by the CDN.
3. **Play** — mpv receives the stream URL and the required `Referer`, `Origin`,
   and `User-Agent` headers. VLC receives `Referer` and `User-Agent`; VLC 3
   cannot set a custom `Origin`.
4. **Download** — the resolved URL is passed to yt-dlp. Subtitles are supplied
   to the player during playback and are not muxed into downloads.

| Provider | Role | Notes |
| --- | --- | --- |
| `imdb_su` | Primary | Follows the embed chain to the vaplayer stream API |
| `vidsrc` | Fallback | Best-effort; browser-gated results are skipped |
| `multiembed` | Fallback | Best-effort; currently Turnstile-gated |

Providers are tried in priority order and may change or disappear over time.
Resolution is best-effort by design.

## Project structure

```text
src/cinebox/
├── __init__.py       CLI and TUI orchestration
├── config.py         configuration, paths, defaults
├── models.py         typed search and stream models
├── search.py         IMDb search and result merging
├── metadata.py       cached IMDb metadata enrichment
├── player.py         mpv and VLC command construction
├── downloader.py     yt-dlp wrapper and quality mapping
├── subtitles.py      keyless subtitle sources and OpenSubtitles
├── settings.py       TUI settings catalog and editor
├── history.py        watch history
├── favorites.py      saved titles
├── discord_rpc.py    optional Rich Presence
├── providers/        streaming provider chain and discovery
└── ui/               terminal UI, themes, posters, components
```

## Development

```bash
uv sync --group dev
uv run pytest --cov=src/cinebox
uv run ruff check src tests
uv run ruff format --check src tests
uv build
```

The test suite is hermetic and does not require network access. CI runs lint,
format, tests, and builds on Python 3.11 through 3.14.

<details>
<summary><strong>Adding a provider</strong></summary>

Create a module under `src/cinebox/providers/`:

```python
from cinebox.models import MediaType, StreamInfo
from cinebox.providers.base import BaseProvider


class ExampleProvider(BaseProvider):
    name = "example"
    priority = 40  # lower runs first; imdb_su is 10, vidsrc is 20

    def resolve(
        self,
        imdb_id: str,
        media_type: MediaType,
        season: int | None = None,
        episode: int | None = None,
    ) -> StreamInfo:
        ...
```

No registry edits are required. Concrete `BaseProvider` subclasses are
discovered automatically. For sources that resolve by keyword instead of IMDb
ID, subclass `KeywordProvider` in
[`src/cinebox/providers/keyword.py`](https://github.com/hosam00/cinebox/blob/main/src/cinebox/providers/keyword.py).

</details>

## Troubleshooting

- **No stream found** — providers can be temporarily unavailable. Retry, try
  another title, and run `cinebox -v` for debug logs.
- **VLC does not open the stream** — verify `vlc --version`. VLC 3 cannot send a
  custom `Origin` header; use mpv if a source requires it.
- **Downloads fail** — confirm `yt-dlp` and `ffmpeg` are installed and on your
  `PATH`.
- **Subtitles are missing** — keyless sources do not cover every title. For
  OpenSubtitles, set the API key, username, and password under
  `[opensubtitles]`.
- **Terminal rendering is broken** — use a terminal at least 80 columns wide.
  Piped or non-interactive sessions fall back to a numbered menu.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](https://github.com/hosam00/cinebox/blob/main/CONTRIBUTING.md) for setup and
pull request expectations. For bug reports, include your OS, player version,
`cinebox --version`, and relevant `-v` logs with credentials removed.

## Roadmap

- [x] PyPI release via Trusted Publishing
- [x] Keyword-search provider interface
- [x] Automatic provider discovery
- [ ] fzf integration and fuzzy search over history/favorites
- [ ] More subtitle sources, including forced subtitles
- [ ] Per-provider enable/disable and health checks
- [ ] A full Stardima keyword provider

## Disclaimer

For content you have the right to consume. `cinebox` indexes publicly
accessible streams and hosts no media. Providers and their CDNs may change or
break at any time. Use at your own risk and respect copyright.

## License

[MIT](https://github.com/hosam00/cinebox/blob/main/LICENSE)

<div align="center">
  <sub>Built with Python, Rich, httpx, and yt-dlp.</sub>
</div>
