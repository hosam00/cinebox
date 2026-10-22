"""Color themes mirrored from ani-cli-arabic.

The active theme colors are exported as module-level COLOR_* constants
based on the value of the ``[ui] theme`` config setting. The palette
matches ani-cli-arabic's 17 themes verbatim so users get the same feel.
"""

from __future__ import annotations

from ..config import load_config

THEMES: dict[str, dict[str, str]] = {
    "blue": {
        "border": "#7eb3d4",
        "title": "#9ac9e3",
        "prompt": "#7eb3d4",
        "loading_spinner": "#9ac9e3",
        "highlight_fg": "#1a2332",
        "highlight_bg": "#7eb3d4",
        "primary_text": "#FFFFFF",
        "secondary_text": "#888888",
        "error": "#d97979",
        "ascii": "#7eb3d4",
    },  # noqa: E501
    "red": {
        "border": "#d97979",
        "title": "#e59393",
        "prompt": "#d97979",
        "loading_spinner": "#e59393",
        "highlight_fg": "#2b1a1a",
        "highlight_bg": "#d97979",
        "primary_text": "#FFFFFF",
        "secondary_text": "#888888",
        "error": "#d97979",
        "ascii": "#d97979",
    },  # noqa: E501
    "green": {
        "border": "#8ba87f",
        "title": "#a3ba98",
        "prompt": "#8ba87f",
        "loading_spinner": "#a3ba98",
        "highlight_fg": "#1a2318",
        "highlight_bg": "#8ba87f",
        "primary_text": "#FFFFFF",
        "secondary_text": "#888888",
        "error": "#d97979",
        "ascii": "#8ba87f",
    },  # noqa: E501
    "purple": {
        "border": "#a88dbd",
        "title": "#bda3cf",
        "prompt": "#a88dbd",
        "loading_spinner": "#bda3cf",
        "highlight_fg": "#1f1a28",
        "highlight_bg": "#a88dbd",
        "primary_text": "#FFFFFF",
        "secondary_text": "#888888",
        "error": "#d97979",
        "ascii": "#a88dbd",
    },  # noqa: E501
    "cyan": {
        "border": "#7ebfbf",
        "title": "#9bd3d3",
        "prompt": "#7ebfbf",
        "loading_spinner": "#9bd3d3",
        "highlight_fg": "#1a2828",
        "highlight_bg": "#7ebfbf",
        "primary_text": "#FFFFFF",
        "secondary_text": "#888888",
        "error": "#d97979",
        "ascii": "#7ebfbf",
    },  # noqa: E501
    "yellow": {
        "border": "#d9c379",
        "title": "#e5d193",
        "prompt": "#d9c379",
        "loading_spinner": "#e5d193",
        "highlight_fg": "#2b2618",
        "highlight_bg": "#d9c379",
        "primary_text": "#FFFFFF",
        "secondary_text": "#888888",
        "error": "#d97979",
        "ascii": "#d9c379",
    },  # noqa: E501
    "pink": {
        "border": "#d9a3ba",
        "title": "#e5b8cd",
        "prompt": "#d9a3ba",
        "loading_spinner": "#e5b8cd",
        "highlight_fg": "#2b1a24",
        "highlight_bg": "#d9a3ba",
        "primary_text": "#FFFFFF",
        "secondary_text": "#888888",
        "error": "#d97979",
        "ascii": "#d9a3ba",
    },  # noqa: E501
    "orange": {
        "border": "#d9a379",
        "title": "#e5b693",
        "prompt": "#d9a379",
        "loading_spinner": "#e5b693",
        "highlight_fg": "#2b1f18",
        "highlight_bg": "#d9a379",
        "primary_text": "#FFFFFF",
        "secondary_text": "#888888",
        "error": "#d97979",
        "ascii": "#d9a379",
    },  # noqa: E501
    "teal": {
        "border": "#6b9a9a",
        "title": "#85b0b0",
        "prompt": "#6b9a9a",
        "loading_spinner": "#85b0b0",
        "highlight_fg": "#182424",
        "highlight_bg": "#6b9a9a",
        "primary_text": "#FFFFFF",
        "secondary_text": "#888888",
        "error": "#d97979",
        "ascii": "#6b9a9a",
    },  # noqa: E501
    "magenta": {
        "border": "#c77eb8",
        "title": "#d79acd",
        "prompt": "#c77eb8",
        "loading_spinner": "#d79acd",
        "highlight_fg": "#281a26",
        "highlight_bg": "#c77eb8",
        "primary_text": "#FFFFFF",
        "secondary_text": "#888888",
        "error": "#d97979",
        "ascii": "#c77eb8",
    },  # noqa: E501
    "lime": {
        "border": "#a3ba8d",
        "title": "#b7cba3",
        "prompt": "#a3ba8d",
        "loading_spinner": "#b7cba3",
        "highlight_fg": "#1f261a",
        "highlight_bg": "#a3ba8d",
        "primary_text": "#FFFFFF",
        "secondary_text": "#888888",
        "error": "#d97979",
        "ascii": "#a3ba8d",
    },  # noqa: E501
    "coral": {
        "border": "#d99382",
        "title": "#e5a899",
        "prompt": "#d99382",
        "loading_spinner": "#e5a899",
        "highlight_fg": "#2b1d1a",
        "highlight_bg": "#d99382",
        "primary_text": "#FFFFFF",
        "secondary_text": "#888888",
        "error": "#d97979",
        "ascii": "#d99382",
    },  # noqa: E501
    "lavender": {
        "border": "#b4a8cf",
        "title": "#c8bedd",
        "prompt": "#b4a8cf",
        "loading_spinner": "#c8bedd",
        "highlight_fg": "#211e2b",
        "highlight_bg": "#b4a8cf",
        "primary_text": "#FFFFFF",
        "secondary_text": "#888888",
        "error": "#d97979",
        "ascii": "#b4a8cf",
    },  # noqa: E501
    "gold": {
        "border": "#c9b87f",
        "title": "#d9ca98",
        "prompt": "#c9b87f",
        "loading_spinner": "#d9ca98",
        "highlight_fg": "#292418",
        "highlight_bg": "#c9b87f",
        "primary_text": "#FFFFFF",
        "secondary_text": "#888888",
        "error": "#d97979",
        "ascii": "#c9b87f",
    },  # noqa: E501
    "mint": {
        "border": "#8dbaa3",
        "title": "#a3cbb7",
        "prompt": "#8dbaa3",
        "loading_spinner": "#a3cbb7",
        "highlight_fg": "#1a2621",
        "highlight_bg": "#8dbaa3",
        "primary_text": "#FFFFFF",
        "secondary_text": "#888888",
        "error": "#d97979",
        "ascii": "#8dbaa3",
    },  # noqa: E501
    "rose": {
        "border": "#d97ea8",
        "title": "#e599bd",
        "prompt": "#d97ea8",
        "loading_spinner": "#e599bd",
        "highlight_fg": "#2b1a23",
        "highlight_bg": "#d97ea8",
        "primary_text": "#FFFFFF",
        "secondary_text": "#888888",
        "error": "#d97979",
        "ascii": "#d97ea8",
    },  # noqa: E501
    "sunset": {
        "border": "#e48b7a",
        "title": "#f0a19a",
        "prompt": "#e48b7a",
        "loading_spinner": "#f0a19a",
        "highlight_fg": "#0a1220",
        "highlight_bg": "#e48b7a",
        "primary_text": "#FFFFFF",
        "secondary_text": "#888888",
        "error": "#d97979",
        "ascii": "#e48b7a",
    },  # noqa: E501
}

THEME_NAMES = list(THEMES.keys())


def _active_theme() -> dict[str, str]:
    config = load_config()
    name = config.get("ui", {}).get("theme", "blue")
    return THEMES.get(name, THEMES["blue"])


_color = _active_theme()
COLOR_ASCII = _color["ascii"]
COLOR_BORDER = _color["border"]
COLOR_TITLE = _color["title"]
COLOR_PROMPT = _color["prompt"]
COLOR_LOADING_SPINNER = _color["loading_spinner"]
COLOR_HIGHLIGHT_FG = _color["highlight_fg"]
COLOR_HIGHLIGHT_BG = _color["highlight_bg"]
COLOR_PRIMARY_TEXT = _color["primary_text"]
COLOR_SECONDARY_TEXT = _color["secondary_text"]
COLOR_ERROR = _color["error"]


def highlight_style() -> str:
    return f"bold {COLOR_HIGHLIGHT_FG} on {COLOR_HIGHLIGHT_BG}"


def reload_theme() -> None:
    """Re-read the active theme from config and refresh the COLOR_* globals."""
    global _color, COLOR_ASCII, COLOR_BORDER, COLOR_TITLE, COLOR_PROMPT
    global COLOR_LOADING_SPINNER, COLOR_HIGHLIGHT_FG, COLOR_HIGHLIGHT_BG
    global COLOR_PRIMARY_TEXT, COLOR_SECONDARY_TEXT, COLOR_ERROR
    _color = _active_theme()
    COLOR_ASCII = _color["ascii"]
    COLOR_BORDER = _color["border"]
    COLOR_TITLE = _color["title"]
    COLOR_PROMPT = _color["prompt"]
    COLOR_LOADING_SPINNER = _color["loading_spinner"]
    COLOR_HIGHLIGHT_FG = _color["highlight_fg"]
    COLOR_HIGHLIGHT_BG = _color["highlight_bg"]
    COLOR_PRIMARY_TEXT = _color["primary_text"]
    COLOR_SECONDARY_TEXT = _color["secondary_text"]
    COLOR_ERROR = _color["error"]
