"""Unit tests for cinebox config management (uses temp config dir)."""

import stat

import pytest

from cinebox import config


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path):
    monkeypatch.setenv("CINEBOX_CONFIG_DIR", str(tmp_path / "config"))
    return tmp_path


def test_config_dir_created(isolated_config):
    d = config.config_dir()
    assert d.exists()
    assert d.name == "cinebox"
    assert stat.S_IMODE(d.stat().st_mode) == 0o700
    assert stat.S_IMODE(config.cache_dir().stat().st_mode) == 0o700


def test_load_config_defaults():
    cfg = config.load_config()
    assert cfg["player"]["default"] == "mpv"
    assert cfg["download"]["quality"] == "1080p"
    assert cfg["provider"]["primary"] == "imdb_su"


def test_ensure_config_writes_file(isolated_config):
    path = config.ensure_config()
    assert path.exists()
    assert "[player]" in path.read_text()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_set_config_keeps_file_private(isolated_config):
    path = config.ensure_config()
    config.set_config("opensubtitles", "api_key", "secret")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert "secret" in path.read_text()


def test_get_single_value(isolated_config):
    assert config.get("player", "default") == "mpv"
    assert config.get("player", "default", "vlc") == "mpv"
    assert config.get("missing", "key", "fallback") == "fallback"


def test_get_merges_user_values(isolated_config):
    config.ensure_config()
    cfg_path = config.config_file()
    cfg_path.write_text("[download]\nquality = '720p'\n")
    assert config.get("download", "quality") == "720p"


def test_set_config_serializes_special_strings(isolated_config):
    import tomllib

    config.ensure_config()
    config.set_config("player", "extra_args", ["--mute", 'a"b', "x\\y"])
    config.set_config("subtitle", "languages", ["en", "ar"])
    parsed = tomllib.loads(config.config_file().read_text())
    assert parsed["player"]["extra_args"] == ["--mute", 'a"b', "x\\y"]
    assert parsed["subtitle"]["languages"] == ["en", "ar"]
    assert stat.S_IMODE(config.config_file().stat().st_mode) == 0o600


def test_set_config_keeps_old_file_when_replace_fails(isolated_config, monkeypatch):
    path = config.ensure_config()
    before = path.read_text()

    def fail_replace(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(config.os, "replace", fail_replace)
    with pytest.raises(OSError):
        config.set_config("player", "default", "vlc")
    assert path.read_text() == before


def test_unknown_quoted_dict_keys_roundtrip(isolated_config):
    import tomllib

    path = config.ensure_config()
    path.write_text('[player]\ndefault = "mpv"\n[custom]\n"a b" = { "x.y" = 1 }\n')
    config.set_config("player", "quality", "720p")
    parsed = tomllib.loads(path.read_text())
    assert parsed["custom"]["a b"]["x.y"] == 1
