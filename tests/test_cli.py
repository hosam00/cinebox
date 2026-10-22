"""CLI-level regression tests for direct play/download commands."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from click.testing import CliRunner

import cinebox as cine
from cinebox.models import MediaType, SearchResult


def _tv_result() -> SearchResult:
    return SearchResult(
        imdb_id="tt0903747",
        title="Breaking Bad",
        media_type=MediaType.TV,
    )


class TestPlayCommand:
    def test_partial_tv_flags_do_not_fall_through_to_movie_flow(self, monkeypatch):
        calls = []

        class FakeApp:
            def _entry_to_result(self, entry):
                return _tv_result()

            def _tv_flow(self, result):
                calls.append("tv_flow")

            def _play_watched_episode(self, *args):
                calls.append("episode")

            def _movie_flow(self, *args):
                calls.append("movie")

        monkeypatch.setattr(cine, "CineApp", lambda: FakeApp())
        result = CliRunner().invoke(cine.play_cmd, ["tt0903747", "-t", "tv", "-s", "1"])

        assert result.exit_code == 0
        assert "requires both --season and --episode" in result.output
        assert calls == []

    def test_complete_tv_flags_play_episode(self, monkeypatch):
        calls = []

        class FakeApp:
            def _entry_to_result(self, entry):
                return _tv_result()

            def _tv_flow(self, result):
                calls.append("tv_flow")

            def _play_watched_episode(self, result, season, episode):
                calls.append((result.imdb_id, season, episode))

            def _movie_flow(self, *args):
                calls.append("movie")

        monkeypatch.setattr(cine, "CineApp", lambda: FakeApp())
        result = CliRunner().invoke(
            cine.play_cmd,
            ["tt0903747", "-t", "tv", "-s", "1", "-e", "2"],
        )

        assert result.exit_code == 0
        assert calls == [("tt0903747", 1, 2)]


class TestDownloadCommand:
    def test_results_menu_quit_does_not_download_last_result(self, monkeypatch):
        app = SimpleNamespace(
            _interactive=True,
            registry=None,
            _goodbye=lambda: setattr(app, "goodbyed", True),
            _hard_download=lambda *args: (_ for _ in ()).throw(AssertionError("must not download")),
        )
        app.ui = SimpleNamespace(results_menu=lambda results: -1)
        app._load = lambda *args, **kwargs: [_tv_result()]
        monkeypatch.setattr(cine, "CineApp", lambda: app)

        result = CliRunner().invoke(cine.download_cmd, ["breaking bad"])

        assert result.exit_code == 0
        assert getattr(app, "goodbyed", False) is True


def test_run_search_reports_network_errors_without_raising(capsys):
    class FakeApp:
        _interactive = False
        registry = None

        def _load(self, *args, **kwargs):
            raise RuntimeError("network down")

        def _message(self, *args, **kwargs):
            raise AssertionError("headless search should use click.echo")

    cine.CineApp.run_search(FakeApp(), "anything")
    assert "Search failed: network down" in capsys.readouterr().err


def test_pick_quit_does_not_return_as_back(monkeypatch):
    app = cine.CineApp()
    app._interactive = True
    app.ui.generic_menu = lambda *args, **kwargs: -1
    goodbyes = []
    monkeypatch.setattr(app, "_goodbye", lambda: goodbyes.append(True))

    with pytest.raises(SystemExit):
        app._pick(["a", "b"], "Pick")
    assert goodbyes == [True]


def test_cineapp_does_not_reset_verbose(monkeypatch):
    monkeypatch.setattr(cine.Log, "verbose", True)
    app = cine.CineApp()
    assert app is not None
    assert cine.Log.verbose is True


def test_version_option_matches_package():
    from importlib.metadata import version

    result = CliRunner().invoke(cine.main, ["--version"])
    assert result.exit_code == 0
    assert version("cinebox") in result.output
