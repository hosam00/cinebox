"""Unit tests for history and favorites persistence."""

import pytest

import cinebox as cine
from cinebox.favorites import FavoritesManager
from cinebox.history import HistoryManager
from cinebox.models import MediaType, SearchResult


@pytest.fixture
def history(tmp_path):
    return HistoryManager(path=tmp_path / "history.json")


@pytest.fixture
def favorites(tmp_path):
    return FavoritesManager(path=tmp_path / "favorites.json")


class TestHistory:
    def test_add_and_list(self, history):
        history.add(
            {
                "imdb_id": "tt001",
                "title": "Alpha",
                "year": 2020,
                "season": None,
                "episode": None,
            }
        )
        entries = history.list()
        assert len(entries) == 1
        assert entries[0]["imdb_id"] == "tt001"

    def test_dedup_by_key(self, history):
        history.add({"imdb_id": "tt001", "title": "Alpha", "season": None, "episode": None})
        history.add({"imdb_id": "tt001", "title": "Alpha v2", "season": None, "episode": None})
        assert len(history.list()) == 1
        assert history.list()[0]["title"] == "Alpha v2"

    def test_tv_entries_tracked_separately(self, history):
        history.add({"imdb_id": "tt001", "title": "Show", "season": 1, "episode": 1})
        history.add({"imdb_id": "tt001", "title": "Show", "season": 1, "episode": 2})
        assert len(history.list()) == 2

    def test_clear(self, history):
        history.add({"imdb_id": "tt001", "title": "Alpha"})
        history.clear()
        assert history.list() == []

    def test_remove(self, history):
        history.add({"imdb_id": "tt001", "title": "Alpha", "season": 1, "episode": 1})
        history.add({"imdb_id": "tt001", "title": "Alpha", "season": 1, "episode": 2})
        history.remove("tt001", season=1, episode=1)
        assert len(history.list()) == 1

    def test_list_sorted_by_recency(self, history):
        history.add({"imdb_id": "tt001", "title": "Alpha"})
        history.add({"imdb_id": "tt002", "title": "Beta"})
        assert history.list()[0]["title"] == "Beta"

    def test_max_entries_capped(self, monkeypatch, tmp_path):
        h = HistoryManager(path=tmp_path / "h.json")
        for i in range(70):
            h.add({"imdb_id": f"tt{i:03d}", "title": f"Title {i}"})
        assert len(h.list()) == 50


class TestFavorites:
    def _make_result(self, imdb_id="tt001", title="Alpha", year=2020):
        return SearchResult(imdb_id=imdb_id, title=title, year=year, media_type=MediaType.MOVIE)

    def test_add_and_has(self, favorites):
        favorites.add(self._make_result())
        assert favorites.has("tt001")
        assert not favorites.has("tt999")

    def test_remove(self, favorites):
        favorites.add(self._make_result())
        favorites.remove("tt001")
        assert not favorites.has("tt001")

    def test_dedup_by_id(self, favorites):
        favorites.add(self._make_result(title="V1"))
        favorites.add(self._make_result(title="V2"))
        assert len(favorites.list()) == 1
        assert favorites.list()[0]["title"] == "V2"

    def test_to_search_result(self, favorites):
        favorites.add(self._make_result())
        entry = favorites.list()[0]
        result = favorites.to_search_result(entry)
        assert result is not None
        assert result.imdb_id == "tt001"
        assert result.media_type == MediaType.MOVIE

    def test_to_search_result_bad_entry(self, favorites):
        assert favorites.to_search_result({"garbage": True}) is None


class TestHistoryLabels:
    def _app(self):
        app = cine.CineApp()
        app._interactive = False
        return app

    def test_movie_entry_with_stray_episode_has_no_season_label(self):
        entry = {"title": "Inception", "media_type": "movie", "season": 1, "episode": 4}
        assert self._app()._history_label(entry) == "Inception"

    def test_tv_entry_shows_season_episode_label(self):
        entry = {"title": "GoT", "media_type": "tv", "season": 1, "episode": 2}
        assert self._app()._history_label(entry) == "GoT — S01E02"

    def test_tv_entry_without_episode_number_has_no_label(self):
        entry = {"title": "GoT", "media_type": "tv", "season": 1}
        assert self._app()._history_label(entry) == "GoT"

    def test_movie_chosen_never_becomes_tv_history(self):
        app = self._app()
        captured = {}
        app.history = type("StubHistory", (), {"add": lambda self, entry: captured.update(entry)})()
        chosen = SearchResult(imdb_id="tt1375666", title="Inception", media_type=MediaType.MOVIE)
        stream = type("StubStream", (), {"title": "Inception"})()
        app._record_history(chosen, 1, 2, stream)
        assert captured["media_type"] == "movie"
        assert captured["season"] is None
        assert captured["episode"] is None

    def test_tv_chosen_keeps_episode_data(self):
        app = self._app()
        captured = {}
        app.history = type("StubHistory", (), {"add": lambda self, entry: captured.update(entry)})()
        chosen = SearchResult(imdb_id="tt1234567", title="GoT", media_type=MediaType.TV)
        stream = type("StubStream", (), {"title": "GoT"})()
        app._record_history(chosen, 1, 2, stream)
        assert captured["media_type"] == "tv"
        assert captured["season"] == 1
        assert captured["episode"] == 2

    def test_record_history_keeps_movie_when_no_episode_args(self):
        app = self._app()
        captured = {}
        app.history = type("StubHistory", (), {"add": lambda self, entry: captured.update(entry)})()
        chosen = SearchResult(imdb_id="tt1375666", title="Inception", media_type=MediaType.MOVIE)
        stream = type("StubStream", (), {"title": "Inception"})()
        app._record_history(chosen, None, None, stream)
        assert captured["media_type"] == "movie"


def test_default_stores_live_in_config_dir_and_migrate(monkeypatch, tmp_path):
    from cinebox import favorites as fav_mod
    from cinebox import history as hist_mod

    config = tmp_path / "config"
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "favorites.json").write_text("[]", encoding="utf-8")
    (cache / "history.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(fav_mod, "config_dir", lambda: config)
    monkeypatch.setattr(fav_mod, "cache_dir", lambda: cache)
    monkeypatch.setattr(hist_mod, "config_dir", lambda: config)
    monkeypatch.setattr(hist_mod, "cache_dir", lambda: cache)

    favorites_mgr = FavoritesManager()
    history_mgr = HistoryManager()
    assert favorites_mgr.path == config / "favorites.json"
    assert history_mgr.path == config / "history.json"
    assert favorites_mgr.path.exists()
    assert history_mgr.path.exists()
    assert (favorites_mgr.path.stat().st_mode & 0o777) == 0o600
    assert (history_mgr.path.stat().st_mode & 0o777) == 0o600


def test_favorite_label_omits_missing_year():
    assert cine._favorite_label({"title": "Alpha", "year": None}) == "Alpha"


def test_duplicate_labels_are_disambiguated():
    assert cine._unique_labels(["Same", "Same", "Other"]) == [
        "Same [1]",
        "Same [2]",
        "Other",
    ]


def test_duplicate_labels_do_not_collide_with_existing_suffix():
    labels = ["Same", "Same", "Same [1]"]
    out = cine._unique_labels(labels)
    assert len(set(out)) == len(labels)
