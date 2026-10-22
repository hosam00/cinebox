"""Unit tests for cinebox search helpers (network-free)."""

import pytest

from cinebox.models import MediaType, SearchResult
from cinebox.search import _suggestion_url


def test_suggestion_url_basic():
    assert (
        _suggestion_url("The Matrix") == "https://v3.sg.media-imdb.com/suggestion/t/the_matrix.json"
    )
    assert _suggestion_url("  incredibles  ") == (
        "https://v3.sg.media-imdb.com/suggestion/i/incredibles.json"
    )


def test_suggestion_url_rejects_empty():
    with pytest.raises(ValueError):
        _suggestion_url("   ")


def test_search_result_filter_type():
    entries = [
        {"id": "tt0000001", "l": "A Movie", "q": "feature", "qid": "movie", "y": 2001},
        {"id": "tt0000002", "l": "A Show", "q": "tv series", "qid": "tvSeries", "y": 2002},
    ]
    movies = [
        r
        for e in entries
        if (r := SearchResult.from_imdb_suggestion(e)) and r.media_type == MediaType.MOVIE
    ]
    tv = [
        r
        for e in entries
        if (r := SearchResult.from_imdb_suggestion(e)) and r.media_type == MediaType.TV
    ]
    assert len(movies) == 1 and movies[0].imdb_id == "tt0000001"
    assert len(tv) == 1 and tv[0].imdb_id == "tt0000002"
