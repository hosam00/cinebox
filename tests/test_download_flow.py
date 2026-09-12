"""Regression tests for the download wiring through CineApp._load.

``_load`` forwards positional args only; earlier code passed keywords
(quality=, filename=, format_selector=) into it, crashing every download
path at runtime. These tests pin the positional contracts.
"""

from pathlib import Path

import cinebox as cine
from cinebox.models import MediaType, SearchResult, StreamInfo


def _app(stream: StreamInfo):
    """Real CineApp with a stubbed registry (no network at construct)."""
    app = cine.CineApp()
    app._interactive = False
    app.registry = type("Reg", (), {"resolve": lambda *a, **k: stream})()
    return app


def _chosen():
    return SearchResult(imdb_id="tt1375666", title="Inception", media_type=MediaType.MOVIE)


class TestDownloadOne:
    def test_forwards_quality_and_filename_positionally(self, monkeypatch):
        stream = StreamInfo(url="x", provider="fake")
        captured = {}

        def fake_download(stream_arg, out, quality, filename=None, format_selector=None):
            captured.update(
                stream=stream_arg, out=out, quality=quality,
                filename=filename, format_selector=format_selector,
            )
            return Path(out) / "out.mkv"

        monkeypatch.setattr(cine, "download_stream", fake_download)
        monkeypatch.setattr(
            cine, "get",
            lambda section, key, default=None: default,
        )
        _app(stream)._download_one(_chosen(), None, None, "480p")
        assert captured["stream"] is stream
        assert captured["quality"] == "480p"
        assert captured["filename"] is None


class TestActDownload:
    def test_download_branch_uses_positional_args(self, monkeypatch):
        stream = StreamInfo(url="x", provider="fake", quality_choices=["1920x800 (4.5 Mbps)"])
        captured = {}

        def fake_download(stream_arg, out, quality, filename=None, format_selector=None):
            captured.update(quality=quality, filename=filename, format_selector=format_selector)
            return Path(out) / "movie.mkv"

        monkeypatch.setattr(cine, "download_stream", fake_download)
        quality_label = "1920x800 (4.5 Mbps)"
        _app(stream)._act(stream, _chosen(), quality_label, None, None, "download")
        assert captured["quality"] == quality_label
        assert captured["format_selector"] == "bestvideo[height<=1080]+bestaudio/best[height<=1080]"


class TestDownloadEpisodes:
    def test_batch_episode_download_forwards_args(self, monkeypatch):
        stream = StreamInfo(url="x", provider="fake", quality_choices=["1280x720 (2.5 Mbps)"])
        captured = []

        def fake_download(stream_arg, out, quality, filename=None, format_selector=None):
            captured.append((quality, filename, format_selector))
            return Path(out) / f"{filename}.mp4"

        monkeypatch.setattr(cine, "download_stream", fake_download)
        monkeypatch.setattr(
            cine, "get",
            lambda section, key, default=None: default,
        )
        _app(stream)._download_episodes(_chosen(), 1, [2, 4])
        assert len(captured) == 2
        assert captured[0][1] == "Inception - S01E02"
        assert captured[1][1] == "Inception - S01E04"
        assert captured[0][2] == "bestvideo[height<=720]+bestaudio/best[height<=720]"
