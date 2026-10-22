"""Unit tests for cinebox utils and player command building."""

from types import SimpleNamespace

import pytest

from cinebox.models import StreamInfo
from cinebox.player import build_mpv_cmd, build_vlc_cmd, play
from cinebox.utils import CineError, PlayerNotFoundError, ensure_command, retry, sanitize_filename


def test_sanitize_filename():
    assert sanitize_filename('Fight Club: "Special" Edition?') == "Fight Club Special Edition"
    assert sanitize_filename('a/b\\c:d*e?f"g<h>i|j') == "abcdefghij"
    assert sanitize_filename("trailing dots...  ") == "trailing dots"


def test_ensure_command_missing():
    with pytest.raises(PlayerNotFoundError):
        ensure_command("definitely-not-a-real-bin-xyz")


def test_retry_no_retry_on_cineerror():
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
    assert cmd[-2:] == ["--", "https://cdn/x/master.m3u8"]


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


def test_build_vlc_cmd_sends_supported_request_headers():
    stream = StreamInfo(
        url="https://cdn/x.m3u8",
        provider="imdb_su",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Origin": "https://player.example",
            "Referer": "https://player.example/embed",
        },
    )
    cmd = build_vlc_cmd(stream, fullscreen=False)
    assert "--http-user-agent=Mozilla/5.0" in cmd
    assert "--http-referrer=https://player.example/embed" in cmd
    # VLC 3 rejects --http-origin outright, which prevented it launching.
    assert not any(arg.startswith("--http-origin=") for arg in cmd)


@pytest.mark.parametrize("url", ["x", "--exec=rm -rf /", "file:///tmp/x.m3u8"])
def test_player_rejects_non_http_stream_url(url):
    stream = StreamInfo(url=url, provider="fake")
    with pytest.raises(ValueError):
        build_mpv_cmd(stream)
    with pytest.raises(ValueError):
        build_vlc_cmd(stream)


def test_play_reports_vlc_input_failure_despite_zero_exit(monkeypatch):
    monkeypatch.setattr("cinebox.player._player_path", lambda player: "/usr/bin/vlc")
    monkeypatch.setattr(
        "cinebox.player.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stderr="main input error: Your input can't be opened\n",
        ),
    )
    with pytest.raises(RuntimeError, match="could not open the stream"):
        play(StreamInfo(url="https://cdn/x.m3u8", provider="fake"), player="vlc")
