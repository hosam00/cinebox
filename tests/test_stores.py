"""Unit tests for history and favorites persistence."""


import pytest

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
        history.add({
            "imdb_id": "tt001", "title": "Alpha", "year": 2020,
            "season": None, "episode": None,
        })
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
