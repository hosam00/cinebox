"""Unit tests for cinebox config management (uses temp config dir)."""


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


def test_load_config_defaults():
    cfg = config.load_config()
    assert cfg["player"]["default"] == "mpv"
    assert cfg["download"]["quality"] == "1080p"
    assert cfg["provider"]["primary"] == "imdb_su"


def test_ensure_config_writes_file(isolated_config):
    path = config.ensure_config()
    assert path.exists()
    assert "[player]" in path.read_text()


def test_get_single_value(isolated_config):
    assert config.get("player", "default") == "mpv"
    assert config.get("player", "default", "vlc") == "mpv"
    assert config.get("missing", "key", "fallback") == "fallback"


def test_get_merges_user_values(isolated_config):
    config.ensure_config()
    cfg_path = config.config_file()
    cfg_path.write_text("[download]\nquality = '720p'\n")
    assert config.get("download", "quality") == "720p"
