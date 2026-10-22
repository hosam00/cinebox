# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-10-22

### Added

- `--version` CLI flag.
- OpenSubtitles account authentication with cached bearer tokens, credential
  fingerprinting, and automatic refresh on expired tokens.
- OpenSubtitles credential rows and secret prompts in the settings TUI.
- Regression coverage for CLI, config, settings, subtitles, downloads, and UI.
- CI format and coverage gates.
- Release workflow tag/version validation and wheel smoke testing.

### Changed

- OpenSubtitles now requires an API key plus account username/password. Key-only
  configurations are ignored because the OpenSubtitles API requires a login.
- `[subtitle] source = "auto"` now merges provider tracks with YIFY, SubSource,
  and OpenSubtitles results, deduplicating identical entries.
- Direct TV playback falls back to the requested episode when provider episode
  metadata is incomplete.
- History and favorites labels are deduplicated.
- VLC receives `Referer` and `User-Agent` headers only; VLC 3 does not support a
  custom `--http-origin` argument. mpv still receives `Origin`.
- Documentation and configuration guidance updated for the new release flow and
  OpenSubtitles credentials.

### Fixed

- VLC failing to launch because of the unsupported `--http-origin` option.
- Post-playback action menu appearing after a failed player launch.
- VLC returning success when the stream could not be opened.
- A broken subtitle candidate aborting the remaining fallback candidates.
- TOML serialization of config keys that require quoting.
- Signed stream URLs leaking into debug logs.
- Episode batch selection mapping picker indices to episode numbers.
- Invalid poster scale values causing rendering errors.

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

[Unreleased]: https://github.com/hosam00/cinebox/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/hosam00/cinebox/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/hosam00/cinebox/releases/tag/v0.1.0
