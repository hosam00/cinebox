"""Configuration management for cinebox.

Config lives in ~/.config/cinebox/config.toml. A defaults-only
config is auto-created when the CLI starts.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"

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
    "opensubtitles": {
        # API key from https://opensubtitles.com (free) plus the account
        # username/password required by the /login endpoint. Treated as a
        # last-resort subtitle source.
        "enabled": True,
        "api_key": "",
        "username": "",
        "password": "",
    },
    "cache": {
        "enabled": True,
        "ttl_hours": 24,
    },
    "ui": {
        "theme": "blue",
        "poster_scale": 1.0,
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
    "opensubtitles",
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
    path.chmod(0o700)
    return path


def config_file() -> Path:
    return config_dir() / "config.toml"


def cache_dir() -> Path:
    path = config_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)
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
                lines.append(f"{key} = {_toml_value(val)}")
            lines.append("")
        write_private(path, "\n".join(lines))
    path.chmod(0o600)
    return path


def get(section: str, key: str, default=None):
    """Fetch a single config value: get('player', 'default', 'mpv')."""
    config = load_config()
    return config.get(section, {}).get(key, default)


def _toml_key(key: object) -> str:
    """Render a TOML bare key, quoting it when necessary."""
    text = str(key)
    if re.fullmatch(r"[A-Za-z0-9_-]+", text):
        return text
    return json.dumps(text, ensure_ascii=False)


def _toml_value(value) -> str:
    """Serialize a Python scalar/list as a TOML value."""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        # TOML basic strings use the same core escapes as JSON.
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    if isinstance(value, dict):
        items = ", ".join(f"{_toml_key(k)} = {_toml_value(v)}" for k, v in value.items())
        return "{" + items + "}"
    raise TypeError(f"Unsupported config value: {value!r}")


def write_private(path: Path, text: str) -> None:
    """Atomically replace *path* with private permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


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
        lines.append(f"[{_toml_key(s)}]")
        for k, v in values.items():
            lines.append(f"{_toml_key(k)} = {_toml_value(v)}")
        lines.append("")
    for s, values in merged.items():
        if s in _CONFIG_SECTIONS:
            continue
        if isinstance(values, dict) and values:
            lines.append(f"[{_toml_key(s)}]")
            for k, v in values.items():
                lines.append(f"{_toml_key(k)} = {_toml_value(v)}")
            lines.append("")
    write_private(path, "\n".join(lines))
