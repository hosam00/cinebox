"""Unit tests for cinebox utils and player command building."""

import pytest

from cinebox.models import StreamInfo
from cinebox.player import build_mpv_cmd, build_vlc_cmd
from cinebox.utils import PlayerNotFoundError, ensure_command, retry, sanitize_filename


def test_sanitize_filename():
    assert sanitize_filename('Fight Club: "Special" Edition?') == 'Fight Club Special Edition'
    assert sanitize_filename('a/b\\c:d*e?f"g<h>i|j') == "abcdefghij"
    assert sanitize_filename("trailing dots...  ") == "trailing dots"


def test_ensure_command_missing():
    with pytest.raises(PlayerNotFoundError):
        ensure_command("definitely-not-a-real-bin-xyz")


def test_retry_no_retry_on_cineerror():
    class CineError(Exception):
        pass

    def _boom():
        raise CineError("boom")

    with pytest.raises(CineError):
        retry(_boom, retries=5)


def test_retry_succeeds_on_transient():
    calls = {"n": 0}

    def _flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("transient")
        return "ok"

    assert retry(_flaky, retries=3, delay=0) == "ok"


def test_build_mpv_cmd():
    stream = StreamInfo(
        url="https://cdn/x/master.m3u8",
        provider="imdb_su",
        headers={"User-Agent": "test", "Referer": "https://p/embed"},
        title="Fight Club",
    )
    cmd = build_mpv_cmd(stream, fullscreen=False)
    assert cmd[0] == "mpv"
    assert "--force-media-title=Fight Club" in cmd
    assert any(a.startswith("--http-header-fields=User-Agent: test") for a in cmd)
    assert cmd[-1] == "https://cdn/x/master.m3u8"


def test_build_mpv_cmd_fullscreen():
    stream = StreamInfo(url="https://cdn/x.m3u8", provider="imdb_su")
    cmd = build_mpv_cmd(stream, fullscreen=True)
    assert "--fs" in cmd


def test_build_vlc_cmd():
    stream = StreamInfo(url="https://cdn/x.m3u8", provider="imdb_su", referer="https://p/embed")
    cmd = build_vlc_cmd(stream, fullscreen=False)
    assert cmd[0] == "vlc"
    assert "--http-referrer=https://p/embed" in cmd
    assert cmd[-1] == "https://cdn/x.m3u8"
