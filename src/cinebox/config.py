"""Configuration management for cinebox.

Config lives in ~/.config/cinebox/config.toml. A defaults-only
config is auto-created on first import.
"""

from __future__ import annotations

import os
from pathlib import Path

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"
)

DEFAULT_HEADERS = {"User-Agent": USER_AGENT}

DEFAULTS: dict[str, dict] = {
    "player": {
        "default": "mpv",
        "fullscreen": True,
        "extra_args": [],
    },
    "download": {
        "movies_dir": "~/Movies",
        "tv_dir": "~/Movies/TV",
        "quality": "1080p",
        "parallel_fragments": 3,
    },
    "provider": {
        "primary": "imdb_su",
        "fallback_enabled": True,
    },
    "subtitle": {
        "enabled": True,
        "default_lang": "en",
        "auto_download": False,
        "source": "auto",
        "languages": ["en", "ar"],
    },
    "cache": {
        "enabled": True,
        "ttl_hours": 24,
    },
    "ui": {
        "theme": "blue",
    },
    "discord": {
        "enabled": False,
        "client_id": "",
    },
    "history": {
        "enabled": True,
        "max_entries": 50,
    },
}

_CONFIG_SECTIONS = (
    "player",
    "download",
    "provider",
    "subtitle",
    "cache",
    "ui",
    "discord",
    "history",
)


def config_dir() -> Path:
    """Return (and create) the ~/.config/cinebox config dir."""
    override = os.environ.get("CINEBOX_CONFIG_DIR")
    base = Path(override) if override else Path.home() / ".config"
    path = base / "cinebox"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_file() -> Path:
    return config_dir() / "config.toml"


def cache_dir() -> Path:
    path = config_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_config() -> dict:
    """Load config from disk, merging over defaults."""
    import tomllib

    merged = {section: dict(values) for section, values in DEFAULTS.items()}
    path = config_file()
    if path.exists():
        try:
            with path.open("rb") as f:
                user = tomllib.load(f)
            for section, values in user.items():
                if section in merged and isinstance(values, dict):
                    merged[section].update(values)
                else:
                    merged[section] = values
        except (tomllib.TOMLDecodeError, OSError) as e:
            print(f"[WARN] Could not read config {path}: {e}")

    return merged


def ensure_config() -> Path:
    """Create ~/.config/cinebox/config.toml if it does not exist."""
    path = config_file()
    if not path.exists():
        lines = ["# cinebox configuration", ""]
        for section, values in DEFAULTS.items():
            lines.append(f"[{section}]")
            for key, val in values.items():
                if isinstance(val, str):
                    lines.append(f"{key} = {val!r}")
                elif isinstance(val, bool):
                    lines.append(f"{key} = {str(val).lower()}")
                else:
                    lines.append(f"{key} = {val!r}")
            lines.append("")
        path.write_text("\n".join(lines))
    return path


def get(section: str, key: str, default=None):
    """Fetch a single config value: get('player', 'default', 'mpv')."""
    config = load_config()
    return config.get(section, {}).get(key, default)


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        items = ", ".join(repr(v) for v in value)
        return f"[{items}]"
    return repr(value)


def set_config(section: str, key: str, value) -> None:
    """Persist a single config value to ~/.config/cinebox/config.toml.

    Reads the current on-disk config, merges the change, and writes the
    whole file back (unknown user sections are preserved).
    """
    if section not in DEFAULTS:
        raise KeyError(f"Unknown config section {section!r}")

    import tomllib

    raw = {}
    path = config_file()
    if path.exists():
        try:
            with path.open("rb") as f:
                raw = tomllib.load(f)
        except (tomllib.TOMLDecodeError, OSError):
            raw = {}

    merged = {s: dict(v) for s, v in DEFAULTS.items()}
    for s, values in raw.items():
        if isinstance(values, dict):
            merged.setdefault(s, {}).update(values)
        else:
            merged[s] = values
    merged[section][key] = value

    lines = ["# cinebox configuration", ""]
    for s in _CONFIG_SECTIONS:
        values = merged.get(s, {})
        if not values:
            continue
        lines.append(f"[{s}]")
        for k, v in values.items():
            lines.append(f"{k} = {_toml_value(v)}")
        lines.append("")
    for s, values in merged.items():
        if s in _CONFIG_SECTIONS:
            continue
        if isinstance(values, dict) and values:
            lines.append(f"[{s}]")
            for k, v in values.items():
                lines.append(f"{k} = {_toml_value(v)}")
            lines.append("")
    path.write_text("\n".join(lines))
