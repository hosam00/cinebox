"""Unit tests for metadata enrichment helpers."""

from cinebox.metadata import (
    Metadata,
    _from_cache,
    _parse_iso_runtime,
    _parse_json_ld,
    _to_cache,
    fetch_metadata,
)


class TestParseIsoRuntime:
    def test_basic(self):
        assert _parse_iso_runtime("PT2H19M") == "2h 19m"

    def test_hours_only(self):
        assert _parse_iso_runtime("PT2H") == "2h"

    def test_minutes_only(self):
        assert _parse_iso_runtime("PT88M") == "88m"

    def test_empty(self):
        assert _parse_iso_runtime("") == ""
        assert _parse_iso_runtime(None) == ""


class TestParseJsonLd:
    def test_valid_block(self):
        page = (
            '<html><script type="application/ld+json">'
            '{"@type":"Movie","aggregateRating":{"ratingValue":8.9,"ratingCount":500},'
            '"genre":["Action"],"duration":"PT2H19M"}'
            "</script></html>"
        )
        data = _parse_json_ld(page)
        assert data is not None
        assert data["aggregateRating"]["ratingValue"] == 8.9

    def test_no_block(self):
        assert _parse_json_ld("<html></html>") is None

    def test_invalid_json(self):
        page = '<script type="application/ld+json">{bad json}</script>'
        assert _parse_json_ld(page) is None


class TestCache:
    def test_roundtrip(self, tmp_path, monkeypatch):
        import cinebox.metadata as mod

        monkeypatch.setattr(mod, "cache_dir", lambda: tmp_path)
        meta = Metadata(rating=[9.0, 500.0], genres=["Action"], runtime="2h")
        _to_cache("tt123", meta)
        loaded = _from_cache("tt123")
        assert loaded is not None
        assert loaded.rating == [9.0, 500.0]
        assert loaded.genres == ["Action"]

    def test_missing_file_returns_none(self, tmp_path, monkeypatch):
        import cinebox.metadata as mod

        monkeypatch.setattr(mod, "cache_dir", lambda: tmp_path)
        assert _from_cache("ttNONE") is None


class TestFetchMetadata:
    def test_returns_metadata(self, tmp_path, monkeypatch):
        import cinebox.metadata as mod

        monkeypatch.setattr(mod, "cache_dir", lambda: tmp_path)

        class FakeResponse:
            text = (
                '<script type="application/ld+json">'
                '{"aggregateRating":{"ratingValue":8.9,"ratingCount":500},'
                '"genre":["Action","Sci-Fi"],"duration":"PT2H19M",'
                '"description":"A great movie","director":[{"name":"Wachowski"}]}'
                "</script>"
            )
            status_code = 200

            def raise_for_status(self):
                pass

        class FakeClient:
            def get(self, url, **kw):
                return FakeResponse()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

        monkeypatch.setattr(mod, "new_http_client", lambda **kw: FakeClient())
        meta = fetch_metadata("tt123")
        assert meta.rating == [8.9, 500.0]
        assert meta.genres == ["Action", "Sci-Fi"]
        assert meta.directors == "Wachowski"

    def test_failure_returns_empty(self, tmp_path, monkeypatch):
        import cinebox.metadata as mod

        monkeypatch.setattr(mod, "cache_dir", lambda: tmp_path)

        def boom(**kw):
            raise RuntimeError("fail")

        monkeypatch.setattr(mod, "new_http_client", boom)
        meta = fetch_metadata("ttFAIL")
        assert meta.is_empty


def test_empty_metadata_is_not_cached(tmp_path, monkeypatch):
    import cinebox.metadata as mod

    monkeypatch.setattr(mod, "cache_dir", lambda: tmp_path)
    _to_cache("ttEMPTY", Metadata())
    assert not (tmp_path / "meta_ttEMPTY.json").exists()


def test_expired_cache_is_ignored(tmp_path, monkeypatch):
    import json
    import time

    import cinebox.metadata as mod

    monkeypatch.setattr(mod, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(mod, "_cache_ttl_seconds", lambda: 10)
    path = tmp_path / "meta_ttOLD.json"
    path.write_text(
        json.dumps({"fetched_at": time.time() - 11, "meta": {"runtime": "2h"}}),
        encoding="utf-8",
    )
    assert _from_cache("ttOLD") is None


def test_cache_disabled_skips_read_and_write(tmp_path, monkeypatch):
    import cinebox.metadata as mod

    monkeypatch.setattr(mod, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(mod, "_cache_enabled", lambda: False)
    meta = Metadata(runtime="2h")
    _to_cache("ttOFF", meta)
    assert not (tmp_path / "meta_ttOFF.json").exists()
    assert _from_cache("ttOFF") is None


def test_director_only_metadata_is_not_empty():
    assert not Metadata(directors="Wachowski").is_empty
