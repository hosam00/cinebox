"""Rich TUI components and screens for cinebox.

Provides a UIManager that renders themed full-screen menus driven by raw
terminal arrow-key input (ported from ani-cli-arabic). It only renders
and captures input; flow orchestration lives in the CLI entry point.
"""

from __future__ import annotations

import shutil
import threading
import time
from dataclasses import dataclass

from rich.align import Align
from rich.box import HEAVY
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich.text import Text

from ..metadata import fetch_metadata_cached
from ..models import SearchResult, SubtitleTrack
from .art import get_header_renderable
from .poster import render_poster
from .terminal import (
    RawTerminal,
    enter_raw_mode_after_input,
    flush_stdin,
    get_key,
    restore_terminal_for_input,
)
from .themes import (
    COLOR_BORDER,
    COLOR_ERROR,
    COLOR_LOADING_SPINNER,
    COLOR_PRIMARY_TEXT,
    COLOR_PROMPT,
    COLOR_SECONDARY_TEXT,
    COLOR_TITLE,
    highlight_style,
)


@dataclass
class EpisodeChoice:
    """Result of the episode picker."""

    action: str  # 'play' | 'download'
    index: int | None
    marked: tuple[int, ...] = ()


@dataclass
class Setting:
    """One editable settings row."""

    label: str
    value_text: str
    edit_id: str


class UIManager:
    """Renders themed screens and captures raw key input."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        self._meta_cache: dict[str, object] = {}
        self._poster_ready: dict[str, bool] = {}
        self._poster_lock = threading.Lock()

    # -- basic helpers -----------------------------------------------------

    def clear(self) -> None:
        self.console.clear()
        # Also erase scrollback — matches ani-cli-arabic's `os.system('clear')`.
        # Without this, every re-render pushes the previous screen down, making
        # the terminal grow on each screen transition.
        self.console.file.write("\033[3J")
        self.console.file.flush()

    def print(self, renderable="") -> None:
        self.console.print(renderable)

    def comfortable_tui(self) -> bool:
        """True when the terminal is wide enough for the full-screen TUI."""
        return shutil.get_terminal_size().columns >= 80

    def ask(self, prompt: str, default: str = "") -> str:
        """Prompt for text input, restoring cooked mode if inside raw mode."""
        if RawTerminal._active_instance is not None:
            restore_terminal_for_input()
        try:
            value = Prompt.ask(prompt, console=self.console)
            return value or default
        finally:
            enter_raw_mode_after_input()

    # -- loading screen ----------------------------------------------------

    def run_with_loading(self, message: str, target_func, *args):
        """Show a spinner while target_func(*args) runs in a thread."""
        self.clear()
        result_container: dict = {}
        done = threading.Event()

        def worker() -> None:
            try:
                result_container["result"] = target_func(*args)
            except Exception as e:  # noqa: BLE001 - surfaced to caller
                result_container["error"] = e
            finally:
                done.set()

        threading.Thread(target=worker, daemon=True).start()

        spinner = Spinner("dots", text=Text(f" {message}", style=COLOR_LOADING_SPINNER))
        panel = Panel(
            Align.center(spinner, vertical="middle"),
            box=HEAVY,
            border_style=COLOR_BORDER,
            padding=(2, 4),
            title=Text("LOADING", style=COLOR_TITLE),
        )
        try:
            with Live(
                Align.center(panel, vertical="middle", height=self.console.height),
                console=self.console,
                refresh_per_second=12,
                screen=True,
            ):
                while not done.is_set():
                    time.sleep(0.05)
        except KeyboardInterrupt:
            done.set()
            raise

        self.clear()
        if "error" in result_container:
            raise result_container["error"]
        return result_container.get("result")

    # -- message panels ----------------------------------------------------

    def render_message(self, title: str, body: str, kind: str = "info") -> None:
        """Centered panel with a 'press any key' prompt."""
        if kind == "error":
            color = COLOR_ERROR
        elif kind == "success":
            color = COLOR_TITLE
        else:
            color = COLOR_PROMPT
        icon = {"error": "✗", "success": "✓", "info": "•"}.get(kind, "•")
        content = Text(f"{icon} {body}", style=COLOR_PRIMARY_TEXT)
        panel = Panel(
            Align.center(content, vertical="middle"),
            title=Text(f"{title}", style=f"bold {color}"),
            subtitle=Text("press any key", style="dim"),
            box=HEAVY,
            border_style=COLOR_BORDER,
            padding=(2, 4),
        )
        self.clear()
        with RawTerminal():
            with Live(
                Align.center(panel, vertical="middle", height=self.console.height),
                console=self.console,
                auto_refresh=False,
                screen=True,
            ) as live:
                live.update(
                    Align.center(panel, vertical="middle", height=self.console.height),
                    refresh=True,
                )
                while True:
                    key = get_key()
                    if key is not None:
                        break

    def render_error_panel(
        self,
        title: str,
        provider_errors: list[str],
        hint: str = "Try again later or pick a different title.",
    ) -> None:
        """Centered red panel listing one failed provider per line."""
        content = Text()
        for err in provider_errors:
            content.append("✗ ", style=COLOR_ERROR)
            content.append(f"{err}\n", style=COLOR_PRIMARY_TEXT)
        content.append(f"— {hint}", style="dim")
        panel = Panel(
            Align.center(content, vertical="middle"),
            title=Text(f"✗ {title}", style=f"bold {COLOR_ERROR}"),
            subtitle=Text("press any key", style="dim"),
            box=HEAVY,
            border_style=COLOR_ERROR,
            padding=(2, 4),
        )
        self.clear()
        with RawTerminal():
            with Live(
                Align.center(panel, vertical="middle", height=self.console.height),
                console=self.console,
                auto_refresh=False,
                screen=True,
            ) as live:
                live.update(
                    Align.center(panel, vertical="middle", height=self.console.height),
                    refresh=True,
                )
                while True:
                    key = get_key()
                    if key is not None:
                        break

    def now_playing(self, title: str, detail: str, quality: str) -> None:
        """Draw a 'Now Playing' panel while the player runs in its own window."""
        content = Text(justify="center")
        content.append("▶ Now Playing\n\n", style=f"bold {COLOR_PROMPT}")
        content.append(f"{title}\n", style=f"bold {COLOR_TITLE}")
        if detail:
            content.append(f"{detail}\n", style=COLOR_PRIMARY_TEXT)
        if quality:
            content.append(f"Quality: {quality}\n\n", style=COLOR_SECONDARY_TEXT)
        content.append("Close your player to return.", style="dim")
        panel = Panel(
            Align.center(content, vertical="middle"),
            title=Text("NOW PLAYING", style=f"bold {COLOR_TITLE}"),
            box=HEAVY,
            border_style=COLOR_BORDER,
            padding=(2, 6),
        )
        self.clear()
        self.print(Align.center(panel, vertical="middle", height=self.console.height))

    # -- main menu ---------------------------------------------------------

    def render_main_menu(self, lb: str, keybinds: str) -> str:
        """Render the home screen and return the raw query line (not raw mode)."""
        flush_stdin()
        return self.ask(f"[{COLOR_PROMPT}]› [/]", default=lb)

    def show_banner(self, keybinds: str) -> None:
        self.clear()
        height = self.console.height
        top_padding = max(0, (height - 14) // 2 - 2)
        self.print(Text("\n" * top_padding))
        self.print(Align.center(get_header_renderable()))
        self.print()
        panel = Panel(
            Text(keybinds, style=COLOR_SECONDARY_TEXT, justify="center"),
            box=HEAVY,
            border_style=COLOR_BORDER,
        )
        self.print(Align.center(panel))
        self.print()

    # -- generic list menu -------------------------------------------------

    def generic_menu(
        self,
        items: list[str],
        title: str,
        subtitle: str | None = None,
    ) -> int | None:
        """Arrow-key list. Returns selected index, None on b/q, -1 on q-quit."""
        selected = 0
        scroll_offset = 0
        target_height = min(self.console.height, 25)
        max_display = max(5, target_height - 5)

        def generate() -> Panel:
            content = Text()
            for idx in range(scroll_offset, min(scroll_offset + max_display, len(items))):
                item = items[idx]
                if idx == selected:
                    content.append(f"▶ {item}\n", style=highlight_style())
                else:
                    content.append(f"  {item}\n", style=COLOR_PRIMARY_TEXT)
            if len(items) > max_display:
                content.append("\n  [dim]▾ scroll for more[/dim]")
            return Panel(
                content,
                title=Text(title, style=COLOR_TITLE),
                box=HEAVY,
                border_style=COLOR_BORDER,
                subtitle=Text(
                    subtitle or "↑↓ Navigate | ENTER Select | b Back | q Quit",
                    style=COLOR_SECONDARY_TEXT,
                ),
                padding=(1, 2),
            )

        self.clear()
        with RawTerminal():
            with Live(
                Align.center(generate(), vertical="middle", height=self.console.height),
                console=self.console,
                auto_refresh=False,
                screen=True,
            ) as live:
                while True:
                    key = get_key()
                    if key == "UP" and selected > 0:
                        selected -= 1
                        if selected < scroll_offset:
                            scroll_offset = selected
                    elif key == "DOWN" and selected < len(items) - 1:
                        selected += 1
                        if selected >= scroll_offset + max_display:
                            scroll_offset = selected - max_display + 1
                    elif key == "ENTER":
                        return selected
                    elif key == "b":
                        return None
                    elif key == "q":
                        return -1
                    else:
                        continue
                    live.update(
                        Align.center(generate(), vertical="middle", height=self.console.height),
                        refresh=True,
                    )

    # -- subtitle picker -----------------------------------------------------

    def subtitle_menu(
        self,
        tracks: list[SubtitleTrack],
        title: str,
    ) -> SubtitleTrack | None:
        """Pick a subtitle track from the ones the provider offers.

        Returns the chosen track, or None to skip subtitles.
        """
        labels = [t.label for t in tracks] + ["No subtitles"]
        try:
            idx = self.generic_menu(
                labels,
                title,
                subtitle="↑↓ Navigate | ENTER Select | b Back | q Quit",
            )
        except (KeyboardInterrupt, EOFError):
            return None
        if idx is None or idx == -1 or idx >= len(tracks):
            return None
        return tracks[idx]

    # -- two-pane results menu ---------------------------------------------

    def _warm_result(
        self,
        result: SearchResult,
        poster_height: int,
        poster_max_chars: int | None = None,
    ) -> None:
        """Background-fetch metadata + poster for a highlighted result."""
        try:
            meta = fetch_metadata_cached(result.imdb_id)
            with self._poster_lock:
                self._meta_cache[result.imdb_id] = meta
        except Exception:  # noqa: BLE001
            pass
        render_poster(result.image_url, poster_height, poster_max_chars)
        with self._poster_lock:
            self._poster_ready[result.imdb_id] = True

    def results_menu(
        self,
        results: list[SearchResult],
        on_favorite=None,
    ) -> int | None:
        """Two-pane browse: results list left, details + poster right.

        Returns the selected index, None for back, -1 to quit.
        ``on_favorite(result)`` is invoked when the user presses F.
        """
        if not results:
            return None
        selected = 0
        scroll_offset = 0
        screen_height = self.console.height
        screen_width = self.console.width
        target_height = min(screen_height, 35)
        if target_height < 20:
            target_height = screen_height
        header_size = 10
        footer_size = 3
        max_display = max(5, target_height - header_size - footer_size - 4)
        body_rows = max(20, screen_height - header_size - footer_size)
        poster_height = max(12, min(45, body_rows - 6))
        pane_inner = max(10, (screen_width * 2 // 5) - 6)
        warmed: set[str] = set()

        def build_layout() -> Layout:
            layout = Layout(name="root")
            layout.split(
                Layout(name="header", size=header_size),
                Layout(name="body"),
                Layout(name="footer", size=footer_size),
            )
            layout["body"].split_row(Layout(name="left", ratio=3), Layout(name="right", ratio=2))
            return layout

        header = get_header_renderable()
        layout = build_layout()

        def make_left() -> Panel:
            content = Text()
            for idx in range(scroll_offset, min(scroll_offset + max_display, len(results))):
                r = results[idx]
                line = f"{r.title}"
                if r.year:
                    line += f" ({r.year})"
                if idx == selected:
                    content.append(f"▶ {line}\n", style=highlight_style())
                else:
                    content.append(f"  {line}\n", style=COLOR_PRIMARY_TEXT)
            if len(results) > max_display:
                content.append("\n[dim]▾ scroll for more[/dim]")
            return Panel(
                content,
                title=Text(f"Results: {len(results)}", style=COLOR_TITLE),
                box=HEAVY,
                border_style=COLOR_BORDER,
                padding=(0, 1),
            )

        def make_right() -> Panel:
            result = results[selected]
            content = Text()
            with self._poster_lock:
                meta = self._meta_cache.get(result.imdb_id)
                ready = self._poster_ready.get(result.imdb_id, False)
            if result.image_url:
                if ready:
                    poster = render_poster(result.image_url, poster_height, pane_inner)
                else:
                    poster = Text("Loading poster…", style="dim")
                content.append(poster)
                content.append("\n\n")
            content.append(f"{result.title}", style=COLOR_TITLE)
            content.append("\n")
            desc = f"{result.media_type.value.upper()} • {result.year or 'year n/a'}"
            content.append(f"{desc}", style=COLOR_SECONDARY_TEXT)
            if result.cast:
                content.append(f"\nCast: [dim]{result.cast}[/dim]")
            if meta is not None and not getattr(meta, "is_empty", False):
                rating = meta.rating[0] if meta.rating else "N/A"
                star = "⭐ " if meta.rating else ""
                content.append(f"\n[bold #FFA500]{star}{rating}[/]")
                if meta.genres:
                    content.append(f" · [dim]{', '.join(meta.genres[:3])}[/dim]")
                if meta.runtime:
                    content.append(f" · {meta.runtime}")
                if meta.plot:
                    content.append(f"\n[dim]{meta.plot}[/dim]")
            if not result.image_url:
                content.append("\n[dim]No poster available[/dim]")
            return Panel(
                content,
                title=Text("Details", style=COLOR_TITLE),
                box=HEAVY,
                border_style=COLOR_BORDER,
                padding=(0, 1),
            )

        def generate() -> Layout:
            layout["header"].update(Align.center(header))
            layout["left"].update(make_left())
            layout["right"].update(make_right())
            layout["footer"].update(
                Panel(
                    Text(
                        "↑↓ Navigate | ENTER Play (F=Favorite) | b Back | q Quit",
                        justify="center",
                        style=COLOR_SECONDARY_TEXT,
                    ),
                    box=HEAVY,
                    border_style=COLOR_BORDER,
                )
            )
            return layout

        self._warm_result(results[0], poster_height, pane_inner)
        warmed.add(results[0].imdb_id)

        self.clear()
        with RawTerminal():
            with Live(generate(), console=self.console, auto_refresh=False, screen=True) as live:
                while True:
                    key = get_key()
                    if key == "UP" and selected > 0:
                        selected -= 1
                        if selected < scroll_offset:
                            scroll_offset = selected
                    elif key == "DOWN" and selected < len(results) - 1:
                        selected += 1
                        if selected >= scroll_offset + max_display:
                            scroll_offset = selected - max_display + 1
                    elif key == "ENTER":
                        return selected
                    elif key == "f":
                        if on_favorite is not None:
                            on_favorite(results[selected])
                        live.update(generate(), refresh=True)
                    elif key == "b":
                        return None
                    elif key == "q":
                        return -1
                    else:
                        continue
                    if results[selected].imdb_id not in warmed:
                        self._warm_result(results[selected], poster_height, pane_inner)
                        warmed.add(results[selected].imdb_id)
                    live.update(generate(), refresh=True)

    # -- quality & action menu ----------------------------------------------

    def quality_menu(self, qualities: list[str], title: str) -> tuple[int, str] | None:
        """Mirror ani-cli-arabic: quality list; ENTER watch, D download."""
        selected = 0
        scroll_offset = 0
        target_height = min(self.console.height, 25)
        max_display = max(5, target_height - 5)

        def generate() -> Panel:
            content = Text()
            for idx in range(scroll_offset, min(scroll_offset + max_display, len(qualities))):
                if idx == selected:
                    content.append(f"▶ {qualities[idx]}\n", style=highlight_style())
                else:
                    content.append(f"  {qualities[idx]}\n", style=COLOR_PRIMARY_TEXT)
            return Panel(
                content,
                title=Text(title, style=COLOR_TITLE),
                box=HEAVY,
                border_style=COLOR_BORDER,
                subtitle=Text("ENTER Watch | D Download | b Back", style=COLOR_SECONDARY_TEXT),
                padding=(2, 4),
            )

        self.clear()
        with RawTerminal():
            with Live(
                Align.center(generate(), vertical="middle", height=self.console.height),
                console=self.console,
                auto_refresh=False,
                screen=True,
            ) as live:
                while True:
                    key = get_key()
                    if key == "UP" and selected > 0:
                        selected -= 1
                    elif key == "DOWN" and selected < len(qualities) - 1:
                        selected += 1
                    elif key == "ENTER":
                        return selected, "watch"
                    elif key == "d":
                        return selected, "download"
                    elif key == "b":
                        return None
                    elif key == "q":
                        return -1, "quit"
                    else:
                        continue
                    live.update(
                        Align.center(generate(), vertical="middle", height=self.console.height),
                        refresh=True,
                    )

    # -- episode picker ------------------------------------------------------

    def episode_menu(
        self,
        episodes: list[int],
        title: str,
        subtitle: str | None = None,
    ) -> EpisodeChoice | None:
        """Episode list with multi-select batch download.

        ENTER plays the highlighted episode; SPACE toggles a mark;
        'd' downloads marked episodes (or highlights if none marked);
        'b'/'q' go back.
        """
        selected = 0
        marked: set[int] = set()
        scroll_offset = 0
        target_height = min(self.console.height, 25)
        max_display = max(5, target_height - 5)

        def generate() -> Panel:
            content = Text()
            for idx in range(scroll_offset, min(scroll_offset + max_display, len(episodes))):
                num = episodes[idx]
                mark = "[*] " if idx in marked else "[ ] "
                line = f"{mark}Episode {num}"
                content.append(f"▶ {line}\n" if idx == selected else f"  {line}\n",
                               style=highlight_style() if idx == selected else COLOR_PRIMARY_TEXT)
            tip = "↑↓ Navigate | ENTER Play | SPACE Mark | D Download | b Back | q Quit"
            return Panel(
                content,
                title=Text(title, style=COLOR_TITLE),
                box=HEAVY,
                border_style=COLOR_BORDER,
                subtitle=Text(subtitle or tip, style=COLOR_SECONDARY_TEXT),
                padding=(1, 2),
            )

        self.clear()
        with RawTerminal():
            with Live(
                Align.center(generate(), vertical="middle", height=self.console.height),
                console=self.console,
                auto_refresh=False,
                screen=True,
            ) as live:
                while True:
                    key = get_key()
                    if key == "UP" and selected > 0:
                        selected -= 1
                        if selected < scroll_offset:
                            scroll_offset = selected
                    elif key == "DOWN" and selected < len(episodes) - 1:
                        selected += 1
                        if selected >= scroll_offset + max_display:
                            scroll_offset = selected - max_display + 1
                    elif key == " ":
                        if selected in marked:
                            marked.remove(selected)
                        else:
                            marked.add(selected)
                    elif key == "ENTER":
                        return EpisodeChoice(
                            action="play", index=selected, marked=tuple(sorted(marked))
                        )
                    elif key == "d":
                        return EpisodeChoice(
                            action="download", index=selected, marked=tuple(sorted(marked))
                        )
                    elif key == "b":
                        return EpisodeChoice(
                            action="back", index=None, marked=tuple(sorted(marked))
                        )
                    elif key == "q":
                        return None
                    else:
                        continue
                    live.update(
                        Align.center(generate(), vertical="middle", height=self.console.height),
                        refresh=True,
                    )

    # -- post-watch menu ------------------------------------------------------

    def post_watch_menu(self, options: list[str] | None = None) -> str | None:
        """Post-playback options, mirroring ani-cli-arabic's 'Finished Watching'.

        *options* may be overridden (e.g. movies show only Replay/Back).
        """
        if options is None:
            options = ["Next Episode", "Previous Episode", "Replay", "Back to List"]
        selected = 0

        def generate() -> Panel:
            content = Text()
            for idx, opt in enumerate(options):
                if idx == selected:
                    content.append(f"▶ {opt}\n", style=highlight_style())
                else:
                    content.append(f"  {opt}\n", style=COLOR_PRIMARY_TEXT)
            return Panel(
                Align.center(content, vertical="middle"),
                title=Text("What next?", style=COLOR_TITLE),
                box=HEAVY,
                padding=(1, 4),
                border_style=COLOR_BORDER,
                subtitle=Text("↑↓ Navigate | ENTER Select | q Quit", style=COLOR_SECONDARY_TEXT),
            )

        self.clear()
        with RawTerminal():
            with Live(
                Align.center(generate(), vertical="middle", height=self.console.height),
                console=self.console,
                auto_refresh=False,
                screen=True,
            ) as live:
                while True:
                    key = get_key()
                    if key == "UP" and selected > 0:
                        selected -= 1
                    elif key == "DOWN" and selected < len(options) - 1:
                        selected += 1
                    elif key == "ENTER":
                        return options[selected]
                    elif key == "q":
                        return "Back to List"
                    else:
                        continue
                    live.update(
                        Align.center(generate(), vertical="middle", height=self.console.height),
                        refresh=True,
                    )

    # -- settings menu --------------------------------------------------------

    def settings_menu(self, settings: list[Setting]) -> str | None:
        """Navigable settings rows. Returns the edit_id of the selected row."""
        lines = [f"{s.label}   [dim]→ {s.value_text}[/dim]" for s in settings]
        idx = self.generic_menu(lines, "Settings", subtitle="Select to edit | b Back | q Quit")
        if idx is None or idx == -1:
            return None
        return settings[idx].edit_id
