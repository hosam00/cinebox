"""Tests for provider auto-discovery, keyword search, and merged search."""

from __future__ import annotations

import pytest

from cinebox.models import MediaType, SearchResult, StreamInfo
from cinebox.providers import (
    ImdbSuProvider,
    MultiEmbedProvider,
    ProviderRegistry,
    ResolutionError,
    VidSrcProvider,
    build_providers,
    build_registry,
    iter_provider_classes,
)
from cinebox.providers.base import BaseProvider
from cinebox.providers.discovery import _import_module
from cinebox.providers.keyword import KeywordProvider
from cinebox.search import search_all


class FakeKeywordProvider(KeywordProvider):
    """Deterministic keyword provider used across the keyword tests."""

    name = "testkw"
    priority = 5
    scheme = "testkw"

    def resolve(self, imdb_id, media_type, season=None, episode=None) -> StreamInfo:
        return StreamInfo(url="https://example.com/stream", provider=self.name)

    def search(self, query, media_type=None) -> list[SearchResult]:
        return [
            SearchResult(
                imdb_id=self.synthetic_id("42"),
                title="Keyword Hit",
                media_type=MediaType.MOVIE,
            ),
            SearchResult(
                imdb_id="tt1111111",
                title="IMDb Lookalike",
                media_type=MediaType.MOVIE,
            ),
        ]


class DuplicateKeywordProvider(KeywordProvider):
    name = "testdup"
    priority = 6
    scheme = "testdup"

    def resolve(self, imdb_id, media_type, season=None, episode=None) -> StreamInfo:
        return StreamInfo(url="https://example.com/dup", provider=self.name)

    def search(self, query, media_type=None) -> list[SearchResult]:
        return [
            SearchResult(
                imdb_id="tt1111111",
                title="Duplicated ID",
                media_type=MediaType.MOVIE,
            ),
            SearchResult(
                imdb_id="tt9999999",
                title="Only From Dup",
                media_type=MediaType.MOVIE,
            ),
        ]


class _ExplodingProvider(BaseProvider):
    name = "boom"

    def __init__(self) -> None:
        raise RuntimeError("constructor failure")

    def resolve(self, imdb_id, media_type, season=None, episode=None) -> StreamInfo:
        raise NotImplementedError


# -- auto-discovery ---------------------------------------------------------


def test_discovery_finds_all_concrete_providers() -> None:
    names = [c.name for c in iter_provider_classes()]
    assert sorted(names) == ["imdb_su", "multiembed", "vidsrc"]


def test_discovery_orders_by_priority() -> None:
    classes = iter_provider_classes()
    assert [c.name for c in classes] == ["imdb_su", "vidsrc", "multiembed"]
    priorities = [c.priority for c in classes]
    assert priorities == sorted(priorities)


def test_build_registry_instantiates_in_priority_order() -> None:
    registry = build_registry()
    assert registry.names() == ["imdb_su", "vidsrc", "multiembed"]

    types = {p.__class__ for p in registry.providers}
    assert types == {ImdbSuProvider, VidSrcProvider, MultiEmbedProvider}


def test_discovery_skips_broken_module(monkeypatch) -> None:
    real_import = _import_module

    def flaky(name: str):
        if name == "vidsrc":
            return None
        return real_import(name)

    monkeypatch.setattr("cinebox.providers.discovery._import_module", flaky)
    names = [c.name for c in iter_provider_classes()]
    assert "vidsrc" not in names
    assert "imdb_su" in names and "multiembed" in names


def test_build_providers_skips_constructor_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        "cinebox.providers.discovery.iter_provider_classes",
        lambda: [_ExplodingProvider],
    )
    providers = build_providers()
    assert providers == []


# -- ResolutionError --------------------------------------------------------


def test_resolution_error_carries_errors() -> None:
    err = ResolutionError(["imdb_su: down", "vidsrc: encrypted"])
    assert err.errors == ["imdb_su: down", "vidsrc: encrypted"]
    assert "imdb_su: down" in str(err)


def test_registry_resolve_collects_all_errors() -> None:
    class AlwaysFails(BaseProvider):
        name = "fails"

        def resolve(self, imdb_id, media_type, season=None, episode=None) -> StreamInfo:
            raise RuntimeError("kaput")

    registry = ProviderRegistry([AlwaysFails(), AlwaysFails()])
    with pytest.raises(ResolutionError) as exc_info:
        registry.resolve("tt0000001", MediaType.MOVIE)
    assert exc_info.value.errors == ["fails: kaput", "fails: kaput"]


# -- KeywordProvider --------------------------------------------------------


def test_synthetic_id_round_trip() -> None:
    provider = FakeKeywordProvider()
    assert provider.synthetic_id("12345") == "testkw:12345"
    assert provider.ref_from_id("testkw:12345") == "12345"


def test_ref_from_id_rejects_foreign_and_imdb() -> None:
    provider = FakeKeywordProvider()
    assert provider.ref_from_id("tt0133093") is None
    assert provider.ref_from_id("otherkw:9") is None


def test_registry_keyword_providers_only_lists_searchable() -> None:
    registry = ProviderRegistry([ImdbSuProvider(), FakeKeywordProvider()])
    names = [p.name for p in registry.keyword_providers()]
    assert names == ["testkw"]


def test_registry_search_merges_and_dedupes() -> None:
    registry = ProviderRegistry([FakeKeywordProvider(), DuplicateKeywordProvider()])
    results = registry.search("inception", MediaType.MOVIE)
    ids = [r.imdb_id for r in results]
    assert ids[0] == "testkw:42"
    assert set(ids) == {"testkw:42", "tt1111111", "tt9999999"}
    assert len(ids) == len(set(ids))
    assert "tt9999999" in ids  # unique to the second provider
    assert "tt1111111" in ids  # shared ID appears only once


def test_registry_search_skips_failing_provider() -> None:
    class BrokenKeyword(KeywordProvider):
        name = "brokenkw"
        scheme = "brokenkw"

        def resolve(self, imdb_id, media_type, season=None, episode=None) -> StreamInfo:
            raise NotImplementedError

        def search(self, query, media_type=None) -> list[SearchResult]:
            raise RuntimeError("endpoint down")

    registry = ProviderRegistry([FakeKeywordProvider(), BrokenKeyword()])
    results = registry.search("inception")
    assert [r.imdb_id for r in results] == ["testkw:42", "tt1111111"]


# -- merged search_all ------------------------------------------------------


def test_search_all_imdb_first_then_keyword(monkeypatch) -> None:
    import importlib

    search_mod = importlib.import_module("cinebox.search")

    def fake_search(query, media_type=None) -> list[SearchResult]:
        return [
            SearchResult(
                imdb_id="tt0000001",
                title="IMDb Result",
                media_type=MediaType.MOVIE,
            )
        ]

    monkeypatch.setattr(search_mod, "search", fake_search)
    registry = ProviderRegistry([FakeKeywordProvider()])
    results = search_all("inception", MediaType.MOVIE, registry)
    ids = [r.imdb_id for r in results]
    assert ids == ["tt0000001", "testkw:42", "tt1111111"]


def test_search_all_without_registry_is_imdb_only(monkeypatch) -> None:
    import importlib

    search_mod = importlib.import_module("cinebox.search")

    def fake_search(query, media_type=None) -> list[SearchResult]:
        return [
            SearchResult(
                imdb_id="tt0000001",
                title="IMDb Result",
                media_type=MediaType.MOVIE,
            )
        ]

    monkeypatch.setattr(search_mod, "search", fake_search)
    results = search_all("inception")
    assert [r.imdb_id for r in results] == ["tt0000001"]


# -- synthetic id validation -------------------------------------------------


def test_search_result_accepts_synthetic_id() -> None:
    result = SearchResult(
        imdb_id="stardima:12345",
        title="Platform Hit",
        media_type=MediaType.MOVIE,
    )
    assert result.imdb_id == "stardima:12345"


def test_search_result_rejects_unscoped_garbage() -> None:
    with pytest.raises(ValueError):
        SearchResult(imdb_id="garbage", title="x", media_type=MediaType.MOVIE)
