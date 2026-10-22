"""cinebox: TUI for searching, streaming, and downloading movies and TV shows."""

from __future__ import annotations

import sys

import click
from rich.align import Align

from .config import cache_dir, ensure_config, get
from .discord_rpc import DiscordRPCManager
from .downloader import (
    download_stream,
    episode_filename,
    format_selector_for_height,
    resolution_height,
)
from .favorites import FavoritesManager
from .history import HistoryManager
from .models import MediaType, SearchResult, StreamInfo, SubtitleTrack
from .player import play, player_exists
from .providers import ResolutionError, build_registry
from .providers.imdb_su import ImdbSuProvider, _discover_player_host
from .search import search_all
from .subtitles import (
    download_subtitle,
    fetch_opensubtitles,
    fetch_subsource,
    fetch_yify,
    pick_track,
)
from .ui import UIManager
from .ui.art import get_goodbye_renderable
from .ui.components import QUIT as UI_QUIT
from .utils import Log, sanitize_filename


def _parse_media_type(raw: str) -> MediaType | None:
    if raw == "movie":
        return MediaType.MOVIE
    if raw == "tv":
        return MediaType.TV
    return None


def _prompt_player() -> str:
    p = get("player", "default", "mpv")
    if not player_exists(p):
        for fallback in ("mpv", "vlc"):
            if player_exists(fallback):
                Log.warn(f"Configured player '{p}' not found, falling back to '{fallback}'.")
                return fallback
    return p


def _unique_labels(labels: list[str]) -> list[str]:
    """Disambiguate duplicate display labels so selection is unambiguous."""
    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    reserved = set(labels)
    used: set[str] = set()
    out: list[str] = []
    for label in labels:
        candidate = label
        if counts[label] > 1:
            suffix = 1
            candidate = f"{label} [{suffix}]"
            while candidate in used or candidate in reserved:
                suffix += 1
                candidate = f"{label} [{suffix}]"
        used.add(candidate)
        out.append(candidate)
    return out


def _favorite_label(entry: dict) -> str:
    title = entry.get("title") or entry.get("imdb_id") or "?"
    year = entry.get("year")
    return f"{title} ({year})" if year else str(title)


class CineApp:
    """Drives the TUI through search → select → play/download flows."""

    def __init__(self, verbose: bool | None = None) -> None:
        if verbose is not None:
            Log.verbose = verbose
        self.ui = UIManager()
        self.history = HistoryManager()
        self.favorites = FavoritesManager()
        self.rpc = DiscordRPCManager()
        self.registry = build_registry()
        self._interactive = self.ui.comfortable_tui() and sys.stdin.isatty() and sys.stdout.isatty()

    # -- entry points ------------------------------------------------------

    def run_menu(self) -> None:
        """Bare `cinebox` opens the home screen menu."""
        if not self._interactive:
            click.echo(
                "No interactive terminal detected. Use 'cinebox search QUERY',\n"
                "'cinebox play <imdb_id>', or 'cinebox download QUERY' instead."
            )
            return
        while True:
            self.ui.show_banner(
                "H: History | F: Favorites | S: Settings | Q: Quit    |    Type to search"
            )
            try:
                query = self.ui.render_main_menu("", "")
            except (KeyboardInterrupt, EOFError):
                self._goodbye()
                return
            action = self._menu_command(query)
            if action == "quit":
                self._goodbye()
                return

    def _menu_command(self, query: str) -> str | None:
        q = query.strip().lower()
        if q in ("q", "quit", "exit"):
            return "quit"
        if q in ("h", "history"):
            self.history_menu()
        elif q in ("f", "favorites"):
            self.favorites_menu()
        elif q in ("s", "settings"):
            self.settings_menu()
        elif not q:
            return None
        else:
            self.run_search(query)
        return None

    def run_search(self, query: str, media_type: MediaType | None = None) -> None:
        """Search, browse results, then route into the play/download flow."""
        try:
            results = self._load(
                f"Searching '{query}'…", search_all, query, media_type, self.registry
            )
        except (KeyboardInterrupt, EOFError):
            return
        except Exception as e:  # noqa: BLE001 - user-facing
            if self._interactive:
                self._message("Search failed", str(e), "error")
            else:
                click.echo(f"Search failed: {e}", err=True)
            return
        if not results:
            if self._interactive:
                self._message("No results", f"No matches for '{query}'.", "error")
            else:
                click.echo(f"No results for '{query}'.")
            return

        def toggle_favorite(result: SearchResult) -> None:
            if self.favorites.has(result.imdb_id):
                self.favorites.remove(result.imdb_id)
                self._message("Favorites", "Removed from favorites.", "info")
            else:
                self.favorites.add(result)
                self._message("Favorites", "Added to favorites.", "success")

        if not self._interactive:
            pick = self._fallback_numbered(
                [r.label for r in results], f"Pick a match for '{query}'"
            )
            if pick is None:
                return
            chosen = next((r for r in results if r.label == pick), None)
            if chosen is not None:
                self._handle_result(chosen, intent="play")
            return

        while True:
            try:
                sel = self.ui.results_menu(results, on_favorite=toggle_favorite)
            except (KeyboardInterrupt, EOFError):
                return
            if sel is None:
                return
            if sel == -1:
                self._goodbye()
                raise SystemExit(0)
            keep = self._handle_result(results[sel], intent="play")
            if not keep:
                return

    # -- TV / movie flows --------------------------------------------------

    def _handle_result(self, chosen: SearchResult, intent: str) -> bool:
        """Route to TV or movie flow.  Returns True to keep browsing."""
        self.rpc.update_status(chosen.title, chosen.media_type.value)
        if chosen.media_type == MediaType.TV:
            return self._tv_flow(chosen)
        return self._movie_flow(chosen, intent)

    def _movie_flow(self, chosen: SearchResult, intent: str) -> bool:
        """Resolve, quality-pick, and play a movie.

        Returns True when the user wants to keep browsing (Back to List /
        Replay exhausted) and False when quitting.
        """
        try:
            stream = self._load(
                f"Resolving '{chosen.title}'…",
                self.registry.resolve,
                chosen.imdb_id,
                MediaType.MOVIE,
                None,
                None,
            )
        except Exception as e:  # noqa: BLE001 - user-facing
            self._resolution_failure(e, "No stream")
            return True
        result = self._quality_and_act(stream, chosen, None, None, intent)
        if result is None:
            return True
        action, acted = result
        if not self._interactive or action != "watch" or not acted:
            return True
        option = self.ui.post_watch_menu(["Replay", "Back to List"])
        if option == "Replay":
            return self._movie_flow(chosen, intent)
        if option == "Quit":
            self._goodbye()
            raise SystemExit(0)
        return True

    def _tv_flow(self, chosen: SearchResult) -> bool:
        """Show the episode list and handle play/download for a TV show.

        Returns True when the user wants to keep browsing results (Back),
        False when quitting to the home menu (q / Ctrl-C).
        """
        try:
            eps_map = self._load(
                f"Loading episodes for '{chosen.title}'…",
                self._episode_map,
                chosen.imdb_id,
            )
        except Exception as e:  # noqa: BLE001 - user-facing
            self._message("No episodes", f"Could not fetch episodes: {e}", "error")
            return True
        if not eps_map:
            self._message("No episodes", "No episode data returned.", "error")
            return True

        seasons = sorted(eps_map.keys(), key=lambda s: int(s) if str(s).isdigit() else 0)
        season = int(seasons[0]) if seasons else 1
        if len(seasons) > 1:
            pick = self._pick([f"Season {s}" for s in seasons], f"{chosen.title} — Season")
            if pick is None:
                return True
            season = int(pick.split()[-1])

        episodes = sorted({int(e) for e in eps_map.get(str(season), [])})
        if not episodes:
            self._message("No episodes", f"No episodes for season {season}.", "error")
            return True

        if not self._interactive:
            pick = self._pick(
                [f"E{e}" for e in episodes],
                f"{chosen.title} — Season {season}",
            )
            if pick is None:
                return True
            self._play_watched_episode(chosen, season, int(pick[1:]), episodes)
            return True

        while True:
            try:
                choice = self.ui.episode_menu(
                    episodes,
                    f"{chosen.title} — Season {season}",
                    subtitle="↑↓ Navigate | ENTER Play | SPACE Mark | D Download | b Back",
                )
            except (KeyboardInterrupt, EOFError):
                return True
            if choice is None:
                return False
            if choice.action == "quit":
                self._goodbye()
                raise SystemExit(0)
            if choice.action == "back":
                return True
            if choice.action == "download":
                if choice.marked:
                    targets = self._marked_episode_numbers(episodes, choice.marked)
                else:
                    targets = [episodes[choice.index]]
                self._download_episodes(chosen, season, targets)
                continue
            self._play_watched_episode(chosen, season, episodes[choice.index], episodes)

    def _play_watched_episode(
        self,
        chosen: SearchResult,
        season: int,
        episode: int,
        episodes: list[int] | None = None,
    ) -> None:
        """Watch episode-by-episode with Next/Previous/Replay/Back navigation.

        Mirrors ani-cli-arabic's ``handle_episode_selection`` inner loop:
        navigation is index-based over the episode list; Next at the last
        episode and Previous at the first show an info message and return.
        """
        if episodes is None:
            try:
                eps_map = self._episode_map(chosen.imdb_id)
            except Exception:  # noqa: BLE001
                eps_map = {}
            episodes = sorted({int(e) for e in eps_map.get(str(season), [])})
            if not episodes:
                episodes = [episode]
            elif episode not in episodes:
                episodes = sorted({*episodes, episode})
        if not episodes:
            self._message("No episodes", f"No episodes for season {season}.", "error")
            return
        try:
            idx = episodes.index(episode)
        except ValueError:
            self._message(
                "No episode",
                f"S{season:02d}E{episode:02d} is not in the episode list.",
                "error",
            )
            return
        while True:
            try:
                stream = self._load(
                    f"Resolving S{season:02d}E{episodes[idx]:02d}…",
                    self.registry.resolve,
                    chosen.imdb_id,
                    MediaType.TV,
                    season,
                    episodes[idx],
                )
            except Exception as e:  # noqa: BLE001 - user-facing
                self._resolution_failure(e, "No stream")
                return
            result = self._quality_and_act(stream, chosen, season, episodes[idx], "play")
            if result is None:
                return
            action, acted = result
            if not self._interactive or action != "watch" or not acted:
                return
            option = self.ui.post_watch_menu()
            if option == "Next Episode":
                if idx + 1 < len(episodes):
                    idx += 1
                    continue
                self._message("Info", "No more episodes!", "info")
                return
            if option == "Previous Episode":
                if idx > 0:
                    idx -= 1
                    continue
                self._message("Info", "This is the first episode.", "info")
                return
            if option == "Replay":
                continue
            if option == "Quit":
                self._goodbye()
                raise SystemExit(0)
            return  # Back to List

    # -- quality / act -----------------------------------------------------

    def _quality_and_act(
        self,
        stream: StreamInfo,
        chosen: SearchResult,
        season: int | None,
        episode: int | None,
        intent: str,
    ) -> tuple[str, bool] | None:
        """Let the user pick a quality and act (watch/download).

        Returns ``(action, acted)`` where action is "watch" or "download";
        None means the user backed out. ``acted`` is False when playback or
        download failed, so callers can skip the post-watch menu.
        """
        qualities = stream.quality_choices or ["1080p (4.5 Mbps)"]
        label = chosen.title
        if season is not None:
            label += f" — S{season:02d}E{episode:02d}"
        action: str
        if not self._interactive:
            picked_idx = -1
            picked = None
            action = "watch" if intent == "play" else "download"
        else:
            try:
                picked = self.ui.quality_menu(qualities, f"{label} — Quality")
            except (KeyboardInterrupt, EOFError):
                return
            if picked is None:
                return
            if picked[1] == "quit":
                self._goodbye()
                raise SystemExit(0)
            picked_idx, action = picked
        if picked_idx is not None and picked:
            quality_label = qualities[picked_idx]
        else:
            quality_label = qualities[-1]
        acted = self._act(stream, chosen, quality_label, season, episode, action)
        return action, acted

    def _act(
        self,
        stream: StreamInfo,
        chosen: SearchResult,
        quality_label: str,
        season: int | None,
        episode: int | None,
        action: str,
    ) -> bool:
        if action == "download":
            out = get("download", "tv_dir" if season is not None else "movies_dir", "~/Movies")
            if season is not None:
                filename = episode_filename(chosen.title, season, episode)
            else:
                filename = None
            height = resolution_height(quality_label)
            try:
                path = self._load(
                    f"Downloading {quality_label}…",
                    download_stream,
                    stream,
                    out,
                    quality_label,
                    filename,
                    format_selector_for_height(height),
                )
                self._message("Done", f"Saved to {path}", "success")
            except Exception as e:  # noqa: BLE001 - user-facing
                self._message("Download failed", str(e), "error")
                return False
            return True
        self._record_history(chosen, season, episode, stream)
        subtitle_file = self._fetch_subtitle(stream, chosen, season, episode)
        player = _prompt_player()
        title = chosen.title
        detail = f"• S{season:02d}E{episode:02d} •" if season is not None else ""
        try:
            self.ui.now_playing(title, detail, quality_label)
            returncode = play(
                stream,
                player=player,
                subtitle_file=subtitle_file,
                fullscreen=bool(get("player", "fullscreen", True)),
                extra_args=list(get("player", "extra_args", []) or []),
            )
        except Exception as e:  # noqa: BLE001 - user-facing
            self._message("Playback error", str(e), "error")
            return False
        if returncode != 0:
            self._message("Playback error", f"{player} exited with code {returncode}.", "error")
            return False
        return True

    def _download_one(
        self, chosen: SearchResult, season: int | None, episode: int | None, quality: str
    ) -> None:
        """Resolve and download a single title/episode at the given quality."""
        mtype = MediaType.TV if season is not None else MediaType.MOVIE
        try:
            stream = self._load(
                f"Resolving {mtype.value}…",
                self.registry.resolve,
                chosen.imdb_id,
                mtype,
                season,
                episode,
            )
        except Exception as e:  # noqa: BLE001 - user-facing
            self._resolution_failure(e, "No stream")
            return
        out = get("download", "tv_dir" if season is not None else "movies_dir", "~/Movies")
        filename = episode_filename(chosen.title, season, episode) if season is not None else None
        try:
            path = self._load(
                f"Downloading ({quality})…",
                download_stream,
                stream,
                out,
                quality,
                filename,
            )
            self._record_history(chosen, season, episode, stream)
            self._message("Done", f"Saved to {path}", "success")
        except Exception as e:  # noqa: BLE001 - user-facing
            self._message("Download failed", str(e), "error")

    @staticmethod
    def _marked_episode_numbers(episodes: list[int], marked: tuple[int, ...]) -> list[int]:
        """Translate episode-picker indices to actual episode numbers."""
        return [episodes[index] for index in marked if 0 <= index < len(episodes)]

    def _download_episodes(self, chosen: SearchResult, season: int, episodes: list[int]) -> None:
        out = get("download", "tv_dir", "~/Movies/TV")
        quality = get("download", "quality", "1080p")
        for ep in episodes:
            try:
                stream = self._load(
                    f"Resolving S{season:02d}E{ep:02d}…",
                    self.registry.resolve,
                    chosen.imdb_id,
                    MediaType.TV,
                    season,
                    ep,
                )
            except Exception as e:  # noqa: BLE001 - user-facing
                self._resolution_failure(e, f"No stream S{season:02d}E{ep:02d}")
                continue
            filename = episode_filename(chosen.title, season, ep)
            try:
                path = self._load(
                    f"Downloading S{season:02d}E{ep:02d}…",
                    download_stream,
                    stream,
                    out,
                    quality,
                    filename,
                )
                self._record_history(chosen, season, ep, stream)
                Log.info(f"Saved: {path}")
            except Exception as e:  # noqa: BLE001 - user-facing
                self._message("Download failed", f"S{season:02d}E{ep:02d}: {e}", "error")

    # -- sub-menus ---------------------------------------------------------

    def history_menu(self) -> None:
        entries = self.history.list()
        if not entries:
            self._message("History", "Nothing watched yet.", "info")
            return
        labels = _unique_labels([self._history_label(e) for e in entries])
        pick = self._pick(labels, "History")
        if pick is None:
            return
        i = labels.index(pick)
        result = self._entry_to_result(entries[i])
        if result is not None:
            self._handle_result(result, intent="play")

    def favorites_menu(self) -> None:
        entries = self.favorites.list()
        if not entries:
            self._message("Favorites", "No favorites yet (press F while browsing).", "info")
            return
        labels = _unique_labels([_favorite_label(e) for e in entries])
        pick = self._pick(labels, "Favorites")
        if pick is None:
            return
        i = labels.index(pick)
        result = self.favorites.to_search_result(entries[i])
        if result is not None:
            self._handle_result(result, intent="play")

    def settings_menu(self) -> None:
        from .settings import SettingsEditor, all_settings  # noqa: PLC0415

        editor = SettingsEditor(self.ui)
        while True:
            pick = self.ui.settings_menu(all_settings())
            if pick is None:
                return
            if pick == -1:
                self._goodbye()
                raise SystemExit(0)
            editor.edit(pick)

    def _hard_download(self, chosen: SearchResult, quality: str) -> None:
        """Direct download path used by the `download` command.

        Movies resolve once and download; TV shows offer the episode
        picker and download the chosen (or marked) episodes.
        """
        if chosen.media_type == MediaType.TV:
            try:
                eps_map = self._load(
                    f"Loading episodes for '{chosen.title}'…", self._episode_map, chosen.imdb_id
                )
            except Exception as e:  # noqa: BLE001 - user-facing
                self._message("No episodes", f"Could not fetch episodes: {e}", "error")
                return
            if not eps_map:
                self._message("No episodes", "No episode data returned.", "error")
                return
            seasons = sorted(eps_map.keys(), key=lambda s: int(s) if str(s).isdigit() else 0)
            season = int(seasons[0]) if seasons else 1
            if len(seasons) > 1:
                pick = self._pick([f"Season {s}" for s in seasons], f"{chosen.title} — Season")
                if pick is None:
                    return
                season = int(pick.split()[-1])
            episodes = sorted({int(e) for e in eps_map.get(str(season), [])})
            if not episodes:
                self._message("No episodes", f"No episodes for season {season}.", "error")
                return
            if self._interactive:
                choice = self.ui.episode_menu(
                    episodes,
                    f"{chosen.title} — Season {season}",
                    subtitle="↑↓ Navigate | SPACE Mark | D Download | b Back",
                )
                if choice is None or choice.action == "back":
                    return
                if choice.action == "quit":
                    self._goodbye()
                    raise SystemExit(0)
                if choice.marked:
                    targets = self._marked_episode_numbers(episodes, choice.marked)
                else:
                    targets = [episodes[choice.index]]
            else:
                nums = [f"E{e}" for e in episodes]
                pick = self._fallback_numbered(nums, f"{chosen.title} S{season}")
                if pick is None:
                    return
                targets = [int(pick[1:])]
            for ep in targets:
                self._download_one(chosen, season, ep, quality)
            return
        self._download_one(chosen, None, None, quality)

    # -- helpers -----------------------------------------------------------

    def _history_label(self, entry: dict) -> str:
        base = entry.get("title", entry.get("imdb_id", "?"))
        if entry.get("year"):
            base += f" ({entry['year']})"
        if entry.get("media_type") == "tv" and entry.get("season") and entry.get("episode"):
            base += f" — S{entry['season']:02d}E{entry['episode']:02d}"
        return base

    def _episode_map(self, imdb_id: str) -> dict[str, list[str]]:
        host = _discover_player_host()
        return ImdbSuProvider.episode_map(imdb_id, host)

    def _load(self, message: str, func, *args):
        """Run with a progress spinner when interactive, else inline."""
        if self._interactive:
            return self.ui.run_with_loading(message, func, *args)
        Log.info(message)
        return func(*args)

    def _message(self, title: str, body: str, kind: str = "info") -> None:
        """Show a message panel (TUI) or a plain line (headless)."""
        if self._interactive:
            self.ui.render_message(title, body, kind)
        else:
            icon = {"error": "[ERROR]", "success": "[OK]  ", "info": "[INFO]"}.get(kind, "[INFO]")
            click.echo(f"{icon} {title}: {body}")

    def _resolution_failure(self, e: Exception, fallback: str) -> None:
        """Report a failed provider chain: per-provider panel or plain line."""
        if not self._interactive:
            click.echo(f"[ERROR] {fallback}: {e}")
        elif isinstance(e, ResolutionError):
            self.ui.render_error_panel(fallback, e.errors)
        else:
            self._message(fallback, str(e), "error")

    def _pick(self, items: list[str], title: str) -> str | None:
        if self._interactive:
            idx = self.ui.generic_menu(items, title)
            if idx == -1:
                self._goodbye()
                raise SystemExit(0)
            if idx is None:
                return None
            return items[idx]
        return self._fallback_numbered(items, title)

    def _fallback_numbered(self, items: list[str], title: str) -> str | None:
        click.echo(title)
        for i, item in enumerate(items, start=1):
            click.echo(f"  {i:>2}. {item}")
        while True:
            try:
                raw = input("Number: ").strip()
            except (EOFError, KeyboardInterrupt):
                return None
            if not raw.isdigit():
                continue
            idx = int(raw) - 1
            if 0 <= idx < len(items):
                return items[idx]

    def _record_history(self, chosen: SearchResult, season, episode, stream: StreamInfo) -> None:
        is_tv = chosen.media_type is MediaType.TV
        self.history.add(
            {
                "imdb_id": chosen.imdb_id,
                "title": stream.title or chosen.title,
                "year": chosen.year,
                "media_type": chosen.media_type.value,
                "image_url": chosen.image_url,
                "cast": chosen.cast,
                "season": season if is_tv else None,
                "episode": episode if is_tv else None,
            }
        )

    def _entry_to_result(self, entry: dict) -> SearchResult | None:
        try:
            return SearchResult(
                imdb_id=entry.get("imdb_id", ""),
                title=entry.get("title", ""),
                year=entry.get("year"),
                media_type=MediaType(entry.get("media_type", "movie")),
                cast=entry.get("cast", ""),
                image_url=entry.get("image_url", ""),
            )
        except (KeyError, ValueError):
            return None

    def _fetch_subtitle(
        self,
        stream: StreamInfo,
        chosen: SearchResult,
        season: int | None = None,
        episode: int | None = None,
    ) -> str | None:
        """Resolve a subtitle file for the stream from the configured source.

        Source is selected by ``[subtitle] source``:
          - ``provider``: only the provider's own tracks (never a network hit
            for titles without them);
          - ``yifysubtitles``: always query YIFYS by IMDb ID (movies only);
          - ``subsource``: always query SubSource by title (+ season/episode
            for episodes);
          - ``opensubtitles``: always query OpenSubtitles by IMDb ID (+
            season/episode), requires an API key and account credentials;
          - ``auto`` (default): merge tracks from every enabled source —
            the provider's own ones plus YIFYS/SubSource and OpenSubtitles
            (when its credentials are set) — and list them all in the picker.

        Every language in ``[subtitle] languages`` (defaults: English +
        Arabic) is searched, with ``default_lang`` taking priority for the
        automatic pick. When several tracks are found, a picker menu is shown
        (mirrors the player's subtitle chooser).
        """
        if not get("subtitle", "enabled", True):
            return None
        source = get("subtitle", "source", "auto")
        lang = get("subtitle", "default_lang", "en")
        langs = list(get("subtitle", "languages", ["en", "ar"]) or [lang])
        if lang and lang in langs:
            langs.remove(lang)
        langs.insert(0, lang)
        tracks = list(stream.subtitles or [])
        use_yify = source in ("auto", "yifysubtitles")
        use_subsource = source in ("auto", "subsource")
        use_opensubtitles = (
            bool(get("opensubtitles", "enabled", True))
            and bool(get("opensubtitles", "api_key", "").strip())
            and bool(get("opensubtitles", "username", "").strip())
            and bool(get("opensubtitles", "password", ""))
            and source in ("auto", "opensubtitles")
        )
        hits: list[SubtitleTrack] = []
        if season is None:
            # YIFYS only indexes movies.
            if use_yify:
                hits += fetch_yify(chosen.imdb_id, langs)
            if use_subsource:
                hits += fetch_subsource(chosen.title, langs, year=chosen.year)
        else:
            # OpenSubtitles first: per-episode and correct where present.
            if use_opensubtitles:
                hits += fetch_opensubtitles(chosen.imdb_id, langs, season=season, episode=episode)
            if use_subsource:
                hits += fetch_subsource(chosen.title, langs, season=season, episode=episode)
        if use_opensubtitles and season is None:
            hits += fetch_opensubtitles(chosen.imdb_id, langs)
        # Merge every enabled source and drop duplicates (provider tracks
        # keep precedence, so identical URLs from external sources vanish).
        seen = {(t.code, t.url) for t in tracks}
        for t in hits:
            if (t.code, t.url) not in seen:
                tracks.append(t)
                seen.add((t.code, t.url))
        if not tracks:
            return None
        if not self._interactive or get("subtitle", "auto_download", False) or len(tracks) == 1:
            track = pick_track(tracks, lang)
        else:
            try:
                track = self.ui.subtitle_menu(tracks, f"Subtitles for '{chosen.title}'")
            except (KeyboardInterrupt, EOFError):
                return None
        if track is UI_QUIT:
            self._goodbye()
            raise SystemExit(0)
        if track is None:
            return None
        safe_id = sanitize_filename(chosen.imdb_id).replace("..", "") or "subs"
        dest = str(cache_dir() / "subtitles" / safe_id)
        if season is not None:
            dest += f"/s{season:02d}e{episode:02d}"
        # Some entries can be broken/empty; retry with the next best
        # candidates until a real subtitle file lands.
        candidates = [candidate for candidate in tracks if candidate is not track]
        candidates.insert(0, track)
        for candidate in candidates[:5]:
            try:
                path = download_subtitle(candidate, dest)
            except Exception as e:  # noqa: BLE001 - subtitles are optional
                Log.debug(f"Subtitle candidate skipped: {e}")
                continue
            if path:
                return str(path)
        return None

    def _goodbye(self) -> None:
        self.ui.clear()
        self.ui.print(Align.center(get_goodbye_renderable()))
        self.ui.print()


# -- click CLI ---------------------------------------------------------------


@click.group(invoke_without_command=True)
@click.version_option(package_name="cinebox")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    """cinebox: Search, stream, download movies and TV shows."""
    Log.verbose = verbose
    ensure_config()
    if ctx.invoked_subcommand is None:
        CineApp(verbose=verbose).run_menu()


@main.command()
@click.argument("query")
@click.option(
    "--type",
    "-t",
    "media_type",
    type=click.Choice(["movie", "tv", "both"]),
    default="both",
)
def search(query: str, media_type: str) -> None:
    """Search IMDb and browse results in the TUI."""
    CineApp().run_search(query, _parse_media_type(media_type))


@main.command("play")
@click.argument("imdb_id")
@click.option("--type", "-t", "media_type", type=click.Choice(["movie", "tv"]), default="movie")
@click.option("--season", "-s", type=int, default=None)
@click.option("--episode", "-e", type=int, default=None)
def play_cmd(imdb_id: str, media_type: str, season: int | None, episode: int | None) -> None:
    """Stream a title directly by IMDb ID."""
    app = CineApp()
    mtype = MediaType.MOVIE if media_type == "movie" else MediaType.TV
    result = app._entry_to_result({"imdb_id": imdb_id, "title": imdb_id, "media_type": mtype.value})
    if result is None:
        click.echo("Invalid IMDb ID.", err=True)
        return
    if mtype == MediaType.TV:
        if season is None and episode is None:
            app._tv_flow(result)
            return
        if season is None or episode is None:
            click.echo("TV playback requires both --season and --episode.", err=True)
            return
        app._play_watched_episode(result, season, episode)
        return
    app._movie_flow(result, "play")


@main.command("download")
@click.argument("query")
@click.option(
    "--quality",
    "-q",
    type=click.Choice(["480p", "720p", "1080p", "best"]),
    default=None,
)
@click.option(
    "--type",
    "-t",
    "media_type",
    type=click.Choice(["movie", "tv", "both"]),
    default="both",
)
def download_cmd(query: str, quality: str | None, media_type: str) -> None:
    """Search and download a title locally."""
    app = CineApp()
    quality = quality or get("download", "quality", "1080p")
    try:
        results = app._load(
            f"Searching '{query}'…", search_all, query, _parse_media_type(media_type), app.registry
        )
    except Exception as e:  # noqa: BLE001 - user-facing
        click.echo(f"Error: {e}", err=True)
        return
    if not results:
        click.echo(f"No results for '{query}'.")
        return

    if app._interactive:
        try:
            sel = app.ui.results_menu(results)
        except (KeyboardInterrupt, EOFError):
            return
        if sel is None:
            return
        if sel == -1:
            app._goodbye()
            raise SystemExit(0)
        chosen = results[sel]
    else:
        pick = app._fallback_numbered([r.label for r in results], f"Pick a match for '{query}'")
        if pick is None:
            return
        chosen = next((r for r in results if r.label == pick), None)
    if chosen is None:
        return
    app._hard_download(chosen, quality)


if __name__ == "__main__":
    main()
