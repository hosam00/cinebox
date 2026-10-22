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
SUBS_SOURCES = ["auto", "provider", "yifysubtitles", "subsource", "opensubtitles"]
DIRS = ["~/Movies", "~/Movies/TV", "~/Videos", "~/Downloads"]


POSTER_SCALES = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.8, 2.0]


def _ui_rows() -> list[Setting]:
    return [
        Setting("Discord RPC", "on" if get("discord", "enabled", False) else "off", "discord_rpc"),
        Setting("Theme", get("ui", "theme", "blue"), "theme"),
        Setting("Poster width", str(get("ui", "poster_scale", 1.0)), "poster_scale"),
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
        Setting(
            "OpenSubtitles enabled",
            "yes" if get("opensubtitles", "enabled", True) else "no",
            "os_enabled",
        ),
        Setting(
            "OpenSubtitles API key",
            "set" if get("opensubtitles", "api_key", "") else "not set",
            "os_api_key",
        ),
        Setting(
            "OpenSubtitles username",
            get("opensubtitles", "username", "") or "not set",
            "os_username",
        ),
        Setting(
            "OpenSubtitles password",
            "set" if get("opensubtitles", "password", "") else "not set",
            "os_password",
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
        elif edit_id == "poster_scale":
            scale_strs = [str(s) for s in POSTER_SCALES]
            picked = self._pick(scale_strs, "Poster width (narrow → wide)")
            if picked:
                set_config("ui", "poster_scale", float(picked))
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
        elif edit_id == "os_enabled":
            set_config(
                "opensubtitles",
                "enabled",
                not get("opensubtitles", "enabled", True),
            )
        elif edit_id in ("os_api_key", "os_username", "os_password"):
            labels = {
                "os_api_key": "API key",
                "os_username": "username",
                "os_password": "password",
            }
            keys = {
                "os_api_key": "api_key",
                "os_username": "username",
                "os_password": "password",
            }
            label = labels[edit_id]
            action = self._pick(
                [f"Replace {label}", f"Clear {label}"],
                f"OpenSubtitles {label}",
            )
            if action == f"Clear {label}":
                set_config("opensubtitles", keys[edit_id], "")
            elif action == f"Replace {label}":
                answer = self.ui.ask(
                    f"OpenSubtitles {label}",
                    default="",
                    secret=edit_id in ("os_api_key", "os_password"),
                )
                if answer.strip():
                    set_config("opensubtitles", keys[edit_id], answer.strip())

    def _reload_theme(self) -> None:
        from .ui.themes import reload_theme  # noqa: PLC0415

        reload_theme()

    def _edit_dir(self, section: str, key: str, choices: list[str]) -> None:
        custom = "Custom path…"
        sel = self._pick([*choices, custom], "Choose directory")
        if sel is None:
            return
        if sel != custom:
            set_config(section, key, sel)
            return
        value = self.ui.ask("Path:", default=get(section, key, ""))
        if value.strip():
            set_config(section, key, value.strip())

    def _edit_int(self, section: str, key: str, lo: int, hi: int) -> None:
        value = self.ui.ask(f"[bold]Enter {key}[/]", default=str(get(section, key, lo)))
        try:
            parsed = int(value)
        except ValueError:
            return
        set_config(section, key, max(lo, min(hi, parsed)))
