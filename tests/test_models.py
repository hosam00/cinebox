"""Unit tests for cinebox models."""

from cinebox.models import MediaType, SearchResult, StreamInfo, _classify_media


def test_media_type_values():
    assert MediaType.MOVIE.value == "movie"
    assert MediaType.TV.value == "tv"


def test_classify_movie():
    assert _classify_media({"q": "feature", "qid": "movie"}) == MediaType.MOVIE
    assert _classify_media({"q": "movie"}) == MediaType.MOVIE


def test_classify_tv():
    assert _classify_media({"q": "tv series", "qid": "tvSeries"}) == MediaType.TV
    assert _classify_media({"qid": "miniseries"}) == MediaType.TV


def test_classify_skips():
    assert _classify_media({"q": "tv episode"}) is None
    assert _classify_media({"q": "video game"}) is None
    assert _classify_media({"qid": "person"}) is None


def test_from_imdb_suggestion_movie():
    entry = {
        "id": "tt0133093",
        "l": "The Matrix",
        "y": 1999,
        "q": "feature",
        "qid": "movie",
        "s": "Keanu Reeves, Laurence Fishburne",
        "i": {"imageUrl": "https://example.com/poster.jpg"},
    }
    r = SearchResult.from_imdb_suggestion(entry)
    assert r is not None
    assert r.imdb_id == "tt0133093"
    assert r.title == "The Matrix"
    assert r.year == 1999
    assert r.media_type == MediaType.MOVIE
    assert r.cast == "Keanu Reeves, Laurence Fishburne"


def test_from_imdb_suggestion_skips_non_media():
    assert SearchResult.from_imdb_suggestion({"l": "Keanu Reeves", "qid": "person"}) is None


def test_label_format():
    r = SearchResult(imdb_id="tt0096895", title="Batman", year=1989, media_type=MediaType.MOVIE)
    assert r.label == "[MOVIE] Batman (1989) — tt0096895"


def test_stream_info_headers_inject_referer():
    s = StreamInfo(url="https://cdn/x/master.m3u8", provider="imdb_su", referer="https://player/embed")
    h = s.get_headers()
    assert h["Referer"] == "https://player/embed"
    s2 = StreamInfo(
        url="https://cdn/x/master.m3u8",
        provider="imdb_su",
        headers={"Referer": "custom"},
        referer="other",
    )
    assert s2.get_headers()["Referer"] == "custom"
