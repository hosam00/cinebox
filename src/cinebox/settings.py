"""Settings catalog for the interactive settings menu.

Each Setting row knows how to render its current value and how to apply
an edit. The UIManager only renders rows and reports which id was picked;
this module (invoked by the CLI) opens specific sub-menus for each kind.
"""

from __future__ import annotations

from .config import get, set_config
from .ui import UIManager
from .ui.components import Setting
from .ui.themes import THEME_NAMES

PLAYERS = ["mpv", "vlc"]
QUALITIES = ["480p", "720p", "1080p", "best"]
LANGS = ["en", "ar", "fr", "es", "de", "hi", "pt", "ru", "ja", "zh"]
SUBS_SOURCES = ["auto", "provider", "yifysubtitles", "subsource"]
DIRS = ["~/Movies", "~/Movies/TV", "~/Videos", "~/Downloads"]


def _ui_rows() -> list[Setting]:
    return [
        Setting("Discord RPC", "on" if get("discord", "enabled", False) else "off", "discord_rpc"),
        Setting("Theme", get("ui", "theme", "blue"), "theme"),
    ]


def _player_rows() -> list[Setting]:
    return [
        Setting("Player", get("player", "default", "mpv"), "player"),
        Setting(
            "Fullscreen",
            "yes" if get("player", "fullscreen", True) else "no",
            "fullscreen",
        ),
    ]


def _download_rows() -> list[Setting]:
    return [
        Setting("Movies dir", get("download", "movies_dir", "~/Movies"), "movies_dir"),
        Setting("TV dir", get("download", "tv_dir", "~/Movies/TV"), "tv_dir"),
        Setting("Default quality", get("download", "quality", "1080p"), "quality"),
        Setting("Parallel fragments", str(get("download", "parallel_fragments", 3)), "fragments"),
    ]


def _subtitle_rows() -> list[Setting]:
    return [
        Setting(
            "Subtitles enabled",
            "yes" if get("subtitle", "enabled", True) else "no",
            "subs_enabled",
        ),
        Setting(
            "Auto-download subs",
            "yes" if get("subtitle", "auto_download", False) else "no",
            "subs_auto",
        ),
        Setting("Subtitle language", get("subtitle", "default_lang", "en"), "subs_lang"),
        Setting("Subtitle source", get("subtitle", "source", "auto"), "subs_source"),
        Setting(
            "Subtitle languages",
            ", ".join(get("subtitle", "languages", ["en", "ar"])),
            "subs_langs",
        ),
    ]


def all_settings() -> list[Setting]:
    return _ui_rows() + _player_rows() + _download_rows() + _subtitle_rows()


class SettingsEditor:
    """Interact with the user to edit a single setting by edit_id."""

    def __init__(self, ui: UIManager) -> None:
        self.ui = ui

    def _pick(self, choices: list[str], title: str) -> str | None:
        index = self.ui.generic_menu(choices, title, subtitle="↑↓ Navigate | ENTER Select | b Back")
        if index is None or index == -1:
            return None
        return choices[index]

    def edit(self, edit_id: str) -> None:
        if edit_id == "discord_rpc":
            set_config("discord", "enabled", not get("discord", "enabled", False))
        elif edit_id == "theme":
            picked = self._pick(THEME_NAMES, "Theme")
            if picked:
                set_config("ui", "theme", picked)
                self._reload_theme()
        elif edit_id == "player":
            picked = self._pick(PLAYERS, "Player")
            if picked:
                set_config("player", "default", picked)
        elif edit_id == "fullscreen":
            set_config("player", "fullscreen", not get("player", "fullscreen", True))
        elif edit_id == "movies_dir":
            self._edit_dir("download", "movies_dir", DIRS)
        elif edit_id == "tv_dir":
            self._edit_dir("download", "tv_dir", DIRS)
        elif edit_id == "quality":
            picked = self._pick(QUALITIES, "Download quality")
            if picked:
                set_config("download", "quality", picked)
        elif edit_id == "fragments":
            self._edit_int("download", "parallel_fragments", 1, 16)
        elif edit_id == "subs_enabled":
            set_config("subtitle", "enabled", not get("subtitle", "enabled", True))
        elif edit_id == "subs_auto":
            set_config("subtitle", "auto_download", not get("subtitle", "auto_download", False))
        elif edit_id == "subs_lang":
            picked = self._pick(LANGS, "Subtitle language")
            if picked:
                set_config("subtitle", "default_lang", picked)
        elif edit_id == "subs_source":
            picked = self._pick(SUBS_SOURCES, "Subtitle source")
            if picked:
                set_config("subtitle", "source", picked)
        elif edit_id == "subs_langs":
            current = ", ".join(get("subtitle", "languages", ["en", "ar"]))
            answer = self.ui.ask("Languages (comma-separated)", default=current)
            if answer.strip():
                langs = [x.strip() for x in answer.split(",") if x.strip()]
                set_config("subtitle", "languages", langs)

    def _reload_theme(self) -> None:
        from .ui.themes import reload_theme  # noqa: PLC0415

        reload_theme()

    def _edit_dir(self, section: str, key: str, choices: list[str]) -> None:
        sel = self._pick(choices, "Choose directory")
        if sel is not None:
            set_config(section, key, sel)
        else:
            value = self.ui.ask("Path:", default=get(section, key, ""))
            if value.strip():
                set_config(section, key, value.strip())

    def _edit_int(self, section: str, key: str, lo: int, hi: int) -> None:
        value = self.ui.ask(f"[bold]Enter {key}[/]",
                            default=str(get(section, key, lo)))
        try:
            parsed = int(value)
        except ValueError:
            return
        set_config(section, key, max(lo, min(hi, parsed)))
