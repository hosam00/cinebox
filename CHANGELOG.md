# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- PyPI publish workflow (todo)

## [0.1.0] - 2026-09-12

### Added
- Public search via IMDb suggestion endpoint (no API key).
- Provider-based stream resolution with automatic fallback:
  `imdb_su` (primary), `vidsrc`, `multiembed`.
- Play in `mpv` or `vlc` with required `Referer`/`Origin`/`User-Agent` headers.
- Interactive TUI: themed panels, arrow-key menus, episode picker, quality menus.
- Download via `yt-dlp` (movies, TV episodes, batch episode marking).
- Subtitles: anonymous fetch for movies and TV (incl. Arabic), no API keys.
- History and favorites persistence (`~/.local/share/cinebox/`).
- Settings menu with 17 themes and editable config values.
- ANSI truecolor poster art (Pillow + numpy).
- Optional Discord Rich Presence.
- Headless/non-interactive fallback for piped & SSH sessions.
- 104 hermetic tests; ruff-clean.