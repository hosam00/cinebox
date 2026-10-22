"""Regression tests for the download wiring through CineApp._load.

``_load`` forwards positional args only; earlier code passed keywords
(quality=, filename=, format_selector=) into it, crashing every download
path at runtime. These tests pin the positional contracts.
"""

from pathlib import Path

import pytest

import cinebox as cine
from cinebox.models import MediaType, SearchResult, StreamInfo
from cinebox.ui import EpisodeChoice


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
                stream=stream_arg,
                out=out,
                quality=quality,
                filename=filename,
                format_selector=format_selector,
            )
            return Path(out) / "out.mkv"

        monkeypatch.setattr(cine, "download_stream", fake_download)
        monkeypatch.setattr(
            cine,
            "get",
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
            cine,
            "get",
            lambda section, key, default=None: default,
        )
        _app(stream)._download_episodes(_chosen(), 1, [2, 4])
        assert len(captured) == 2
        assert captured[0][0] == "1080p"
        assert captured[1][0] == "1080p"
        assert captured[0][1] == "Inception - S01E02"
        assert captured[1][1] == "Inception - S01E04"
        assert captured[0][2] is None


class TestHardDownload:
    def test_marked_picker_indices_map_to_episode_numbers(self, monkeypatch):
        app = _app(StreamInfo(url="x", provider="fake"))
        app._interactive = True
        chosen = SearchResult(
            imdb_id="tt0903747",
            title="Breaking Bad",
            media_type=MediaType.TV,
        )
        monkeypatch.setattr(app, "_load", lambda *args, **kwargs: {"1": ["1", "2", "4"]})
        monkeypatch.setattr(
            app.ui,
            "episode_menu",
            lambda *args, **kwargs: EpisodeChoice(action="download", index=0, marked=(1, 2)),
        )
        captured = []
        monkeypatch.setattr(app, "_download_one", lambda *args: captured.append(args))

        app._hard_download(chosen, "720p")

        assert [args[2] for args in captured] == [2, 4]

    def test_noninteractive_hard_download_selects_season(self, monkeypatch):
        app = _app(StreamInfo(url="x", provider="fake"))
        app._interactive = False
        chosen = SearchResult(
            imdb_id="tt0903747",
            title="Breaking Bad",
            media_type=MediaType.TV,
        )
        monkeypatch.setattr(
            app,
            "_load",
            lambda *args, **kwargs: {
                "1": ["1"],
                "2": ["1"],
            },
        )
        monkeypatch.setattr(app, "_pick", lambda items, title: "Season 2")
        monkeypatch.setattr(app, "_fallback_numbered", lambda items, title: "E1")
        captured = []
        monkeypatch.setattr(app, "_download_one", lambda *args: captured.append(args))

        app._hard_download(chosen, "720p")

        assert len(captured) == 1
        assert captured[0][1] == 2
        assert captured[0][2] == 1


class TestTvFlow:
    def test_marked_picker_indices_map_to_episode_numbers(self):
        chosen = SearchResult(
            imdb_id="tt0903747",
            title="Breaking Bad",
            media_type=MediaType.TV,
        )
        captured = []
        choices = iter(
            [
                EpisodeChoice(action="download", index=0, marked=(1, 2)),
                None,
            ]
        )

        class FakeUi:
            def episode_menu(self, *args, **kwargs):
                return next(choices)

        class FakeApp:
            _interactive = True
            ui = FakeUi()
            _marked_episode_numbers = staticmethod(cine.CineApp._marked_episode_numbers)

            def _episode_map(self, imdb_id):
                return {}

            def _load(self, message, func, *args):
                return {"1": ["1", "2", "4"]}

            def _download_episodes(self, chosen, season, episodes):
                captured.append((season, episodes))

            def _message(self, *args, **kwargs):
                pass

        assert cine.CineApp._tv_flow(FakeApp(), chosen) is False
        assert captured == [(1, [2, 4])]

    def test_headless_uses_numbered_episode_picker(self):
        chosen = SearchResult(
            imdb_id="tt0903747",
            title="Breaking Bad",
            media_type=MediaType.TV,
        )
        captured = {}

        class FakeApp:
            _interactive = False

            def _episode_map(self, imdb_id):
                return {}

            def _load(self, message, func, *args):
                return {"1": ["1", "2"]}

            def _pick(self, items, title):
                assert items == ["E1", "E2"]
                return "E2"

            def _play_watched_episode(self, chosen, season, episode, episodes):
                captured.update(season=season, episode=episode, episodes=episodes)

            def _message(self, *args, **kwargs):
                pass

        assert cine.CineApp._tv_flow(FakeApp(), chosen) is True
        assert captured == {"season": 1, "episode": 2, "episodes": [1, 2]}


class TestPlayWatchedEpisode:
    def test_unknown_episode_does_not_fall_back_to_first(self):
        chosen = SearchResult(
            imdb_id="tt0903747",
            title="Breaking Bad",
            media_type=MediaType.TV,
        )
        messages = []

        class FakeApp:
            def _message(self, title, body, kind="info"):
                messages.append((title, body, kind))

            def _load(self, *args, **kwargs):
                raise AssertionError("must not resolve an unknown episode")

        cine.CineApp._play_watched_episode(FakeApp(), chosen, 1, 99, [1, 2])

        assert messages
        assert "not in the episode list" in messages[0][1]


class TestPlaybackFailure:
    def test_nonzero_player_exit_is_reported(self, monkeypatch):
        stream = StreamInfo(url="https://cdn.example/ep.m3u8", provider="fake")
        app = _app(stream)
        app._interactive = True
        messages = []
        monkeypatch.setattr(app, "_fetch_subtitle", lambda *args: None)
        monkeypatch.setattr(cine, "_prompt_player", lambda: "vlc")
        monkeypatch.setattr(app.ui, "now_playing", lambda *args: None)
        monkeypatch.setattr(app, "_message", lambda *args, **kwargs: messages.append(args))
        monkeypatch.setattr(cine, "play", lambda *args, **kwargs: 1)

        assert app._act(stream, _chosen(), "1080p", None, None, "watch") is False
        assert messages
        assert "exited with code 1" in messages[-1][1]

    def test_failed_playback_skips_post_watch_menu(self, monkeypatch):
        app = _app(StreamInfo(url="https://cdn.example/ep.m3u8", provider="fake"))
        app._interactive = True
        app._load = lambda *args: StreamInfo(url="https://cdn.example/ep.m3u8", provider="fake")
        app._quality_and_act = lambda *args: ("watch", False)
        monkeypatch.setattr(
            app.ui,
            "post_watch_menu",
            lambda *args: pytest.fail("post-watch menu shown after failed playback"),
        )

        app._play_watched_episode(_chosen(), 1, 1, [1])


class TestDirectEpisodePlayback:
    def test_missing_episode_map_uses_requested_episode(self):
        app = _app(StreamInfo(url="https://cdn.example/ep.m3u8", provider="fake"))
        app._interactive = True
        app._episode_map = lambda *args: {}
        app._load = lambda *args: StreamInfo(url="https://cdn.example/ep.m3u8", provider="fake")
        seen = {}

        def quality_and_act(stream, chosen, season, episode, intent):
            seen.update(season=season, episode=episode)
            return "watch", True

        app._quality_and_act = quality_and_act
        app.ui.post_watch_menu = lambda *args: "Back to List"

        app._play_watched_episode(_chosen(), 2, 5)
        assert seen == {"season": 2, "episode": 5}
