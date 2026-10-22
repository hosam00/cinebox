"""Unit tests for the downloader helpers."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from cinebox import downloader
from cinebox.downloader import (
    _format_selector,
    episode_filename,
    format_selector_for_height,
    resolution_height,
)
from cinebox.models import StreamInfo


def test_format_selector_named_qualities():
    assert "height<=480" in _format_selector("480p")
    assert "height<=720" in _format_selector("720p")
    assert "height<=1080" in _format_selector("1080p")
    assert _format_selector("best") == "bestvideo+bestaudio/best"


def test_format_selector_unknown_raises():
    with pytest.raises(ValueError):
        _format_selector("144p")


def test_resolution_height_parses_label():
    assert resolution_height("1920x800 (4.5 Mbps)") == 800
    assert resolution_height("1280x534 (2.3 Mbps)") == 534
    assert resolution_height("640x266 (0.7 Mbps)") == 266


def test_resolution_height_defaults_to_1080():
    assert resolution_height("unknown") == 1080
    assert resolution_height("4K Ultra HD") == 2160


def test_format_selector_for_height():
    assert "height<=480" in format_selector_for_height(480)
    assert "height<=720" in format_selector_for_height(700)
    assert "height<=1080" in format_selector_for_height(1080)
    assert "height<=2160" in format_selector_for_height(2160)


def test_episode_filename():
    assert episode_filename("Breaking Bad", 1, 1) == "Breaking Bad - S01E01"
    assert episode_filename("Breaking Bad", 12, 305) == "Breaking Bad - S12E305"


def test_download_stream_finds_title_with_spaces_percent_and_brackets(tmp_path, monkeypatch):
    stream = StreamInfo(
        url="https://cdn.example/movie.m3u8",
        provider="fake",
        title="100% Movie [2024]",
    )
    captured: dict[str, list[str]] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        template = Path(cmd[cmd.index("--output") + 1])
        name = template.name.replace("%%", "%").replace("%(ext)s", "mkv")
        (tmp_path / name).write_bytes(b"video")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(downloader, "_which_ytdlp", lambda: "yt-dlp")
    monkeypatch.setattr(downloader, "get", lambda *args, **kwargs: 1)
    monkeypatch.setattr(downloader.subprocess, "run", fake_run)

    result = downloader.download_stream(stream, str(tmp_path))

    assert result == tmp_path / "100% Movie [2024].mkv"
    assert "--restrict-filenames" not in captured["cmd"]
    assert captured["cmd"][-2:] == ["--", "https://cdn.example/movie.m3u8"]
    assert captured["cmd"][captured["cmd"].index("--output") + 1].endswith(
        "100%% Movie [2024].%(ext)s"
    )


def test_download_stream_rejects_non_http_url(tmp_path):
    stream = StreamInfo(url="--exec=rm -rf /", provider="fake")
    with pytest.raises(ValueError):
        downloader.download_stream(stream, str(tmp_path))


def test_download_stream_captures_output_and_reports_tail(tmp_path, monkeypatch):
    stream = StreamInfo(url="https://cdn.example/x.m3u8", provider="fake")
    monkeypatch.setattr(downloader, "_which_ytdlp", lambda: "yt-dlp")
    monkeypatch.setattr(downloader, "get", lambda *args, **kwargs: 1)

    def fake_run(cmd, **kwargs):
        assert kwargs == {"capture_output": True, "text": True}
        return SimpleNamespace(returncode=2, stdout="", stderr="ERROR: nope\n")

    monkeypatch.setattr(downloader.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="ERROR: nope"):
        downloader.download_stream(stream, str(tmp_path))
