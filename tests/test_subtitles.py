"""Unit tests for subtitle tracks, download, and the YIFYS/SubSource fallback."""

import gzip
import io
import stat
import zipfile
from contextlib import contextmanager
from pathlib import Path

import cinebox as cine
import cinebox.subtitles as subs
from cinebox.models import MediaType, SearchResult, StreamInfo, SubtitleTrack
from cinebox.providers.imdb_su import ImdbSuProvider
from cinebox.subtitles import download_subtitle, pick_track


class TestFromApi:
    def test_valid_entry(self):
        track = SubtitleTrack.from_api(
            {"lang": "English - eng", "code": "en", "url": "https://vidapi.cloud/x/eng.srt"}
        )
        assert track is not None
        assert track.code == "en"
        assert track.url.endswith(".srt")
        assert track.label == "English - eng"

    def test_missing_url_returns_none(self):
        assert SubtitleTrack.from_api({"lang": "X"}) is None

    def test_dict_support_in_download(self):
        parsed = SubtitleTrack.from_api({"url": "https://x/y.ar.srt", "lang": "ar"})
        assert parsed is not None and parsed.code == ""


class TestPickTrack:
    def _tracks(self):
        return [
            SubtitleTrack(lang="English - eng", code="en", url="en.srt"),
            SubtitleTrack(lang="العربية - ara", code="ar", url="ar.srt"),
        ]

    def test_code_match(self):
        assert pick_track(self._tracks(), "ar").code == "ar"
        assert pick_track(self._tracks(), "en").code == "en"

    def test_language_substring_match(self):
        tracks = [
            SubtitleTrack(lang="Brazilian Portuguese - por", code="pt", url="pt.srt"),
            SubtitleTrack(lang="English - eng", code="en", url="en.srt"),
        ]
        assert pick_track(tracks, "portuguese").code == "pt"
        # no code or label match -> fall back to first track
        assert pick_track(tracks, "spanish").code == "pt"

    def test_empty_language_returns_first(self):
        assert pick_track(self._tracks(), "").code == "en"

    def test_no_tracks(self):
        assert pick_track([], "en") is None

    def test_unsupported_lang_falls_back_to_first(self):
        assert pick_track(self._tracks(), "zz").code == "en"


class TestDownloadSubtitle:
    def test_writes_srt(self, tmp_path, monkeypatch):
        class Resp:
            def raise_for_status(self):
                pass

        class Client:
            def get(self, url):
                assert url == "https://vidapi.cloud/x/eng.srt"
                resp = Resp()
                resp.content = b"WEBVTT\n\n1\n00:00:01 --> 00:00:03\nHello\n"
                return resp

        order = []

        @contextmanager
        def fake_client(**kwargs):
            order.append(("open", kwargs))
            yield Client()
            order.append(("close", kwargs))

        monkeypatch.setattr(subs, "new_http_client", fake_client)
        track = SubtitleTrack(lang="English - eng", code="en", url="https://vidapi.cloud/x/eng.srt")
        path = download_subtitle(track, tmp_path)
        assert path == tmp_path / "en.srt"
        assert b"WEBVTT" in path.read_bytes()
        assert order[0][0] == "open"

    def test_skips_bad_url(self, tmp_path, monkeypatch):
        class Resp:
            def raise_for_status(self):
                raise ConnectionError("nope")

        class Client:
            def get(self, url):
                return Resp()

        @contextmanager
        def fake_client(**kwargs):
            yield Client()

        monkeypatch.setattr(subs, "new_http_client", fake_client)
        track = SubtitleTrack(lang="x", code="en", url="https://bad/x.en.srt")
        assert download_subtitle(track, tmp_path) is None

    def test_accepts_plain_dict(self, tmp_path, monkeypatch):
        class Resp:
            content = b"1\n00:00:01,000 --> 00:00:03,000\nHello\n"

            def raise_for_status(self):
                pass

        class Client:
            def get(self, url):
                return Resp()

        @contextmanager
        def fake_client(**kwargs):
            yield Client()

        monkeypatch.setattr(subs, "new_http_client", fake_client)
        path = download_subtitle({"url": "https://x/sub.ar.srt", "lang": "ar"}, tmp_path)
        assert path is not None
        assert path.suffix == ".srt"


class TestDecodeSubtitle:
    def test_plain_srt_passes(self):
        srt = b"1\n00:00:01,000 --> 00:00:03,000\nHello\n"
        assert subs._decode_subtitle(srt) == srt

    def test_gzip_payload_decoded(self):
        srt = b"1\n00:00:01,000 --> 00:00:03,000\nHello\n"
        assert subs._decode_subtitle(gzip.compress(srt)) == srt

    def test_zip_extracts_srt(self):
        srt = b"1\n00:00:01,000 --> 00:00:03,000\nMerhaba\n"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("movie.ar.srt", srt)
        assert subs._decode_subtitle(buf.getvalue()) == srt

    def test_zip_picks_largest_subtitle(self):
        small = b"1\n00:00:01,000 --> 00:00:03,000\nHi\n"
        big = b"1\n00:00:01,000 --> 00:00:03,000\nLonger dialog line here\n"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("a.srt", small)
            zf.writestr("b.srt", big)
        out = subs._decode_subtitle(buf.getvalue())
        assert out == big

    def test_rejects_html_page(self):
        assert subs._decode_subtitle(b"<html><body>captcha</body></html>") is None

    def test_rejects_non_subtitle_bytes(self):
        assert subs._decode_subtitle(b"just some random text") is None

    def test_cp1256_arabic_normalized_to_utf8(self):
        srt = "1\n00:00:01,000 --> 00:00:03,000\nالترجمة من المشاهد\n".encode("cp1256")
        out = subs._decode_subtitle(srt, code="ar")
        assert out is not None
        out.decode("utf-8")  # must now be valid UTF-8
        assert "الترجمة" in out.decode("utf-8")


class TestProviderAttachesSubtitles:
    def test_resolve_parses_default_subs(self, monkeypatch):
        import cinebox.providers.imdb_su as mod

        def fake_fetch(*args, **kwargs):
            return {
                "status_code": "200",
                "default_subs": [
                    {"lang": "English - eng", "code": "en", "url": "https://v/e.srt"},
                ],
                "data": {
                    "title": "The Mummy",
                    "stream_urls": ["https://cd/hls/master.m3u8"],
                    "imdb_id": "tt0120616",
                },
            }

        monkeypatch.setattr(mod, "fetch_stream_api", fake_fetch)
        monkeypatch.setattr(mod, "_parse_quality_variants", lambda *a, **k: [])

        provider = ImdbSuProvider()
        media = MediaType.MOVIE
        stream = provider.resolve("tt0120616", media)
        assert len(stream.subtitles) == 1
        assert stream.subtitles[0].code == "en"
        assert stream.subtitles[0].url == "https://v/e.srt"

    def test_resolve_without_subs(self, monkeypatch):
        import cinebox.providers.imdb_su as mod

        def fake_fetch(*args, **kwargs):
            return {
                "status_code": "200",
                "default_subs": [],
                "data": {
                    "title": "X",
                    "stream_urls": ["https://cd/hls/master.m3u8"],
                    "imdb_id": "tt0000001",
                },
            }

        monkeypatch.setattr(mod, "fetch_stream_api", fake_fetch)
        monkeypatch.setattr(mod, "_parse_quality_variants", lambda *a, **k: [])

        provider = ImdbSuProvider()
        media = MediaType.MOVIE
        stream = provider.resolve("tt0000001", media)
        assert stream.subtitles == []


def _row(row_id: int, rating: int, lang: str, slug: str, releases: list[str]):
    rel = "<br />".join(releases)
    return (
        f'<tr data-id="{row_id}">'
        f'<td class="rating-cell"><span class="label label-success">{rating}</span></td>'
        f'<td class="flag-cell"><span class="flag flag-"></span>'
        f'<span class="sub-lang">{lang}</span></td>'
        f'<td><a href="/subtitles/{slug}">{rel}</a></td>'
        f'<td class="other-cell"></td><td class="uploader-cell">u</td></tr>'
    )


def _movie_html(*rows: str) -> str:
    return "<html><body>" + "".join(rows) + "</body></html>"


class TestYify:
    @staticmethod
    def _disable_cache(monkeypatch):
        monkeypatch.setattr(subs, "get", lambda *a: False if a[1] == "enabled" else a[2])

    def test_parse_and_sort_by_rating(self, monkeypatch):
        self._disable_cache(monkeypatch)
        html = _movie_html(
            _row(1, 20, "English", "mov-1", ["En.x264"]),
            _row(2, 60, "Arabic", "mov-2", ["Ar.DVDRip"]),
            _row(3, 10, "English", "mov-3", ["En.720p"]),
        )
        tracks = subs._parse_yify_movie(html, ["ar", "en"])
        assert len(tracks) == 3
        codes = [t.code for t in tracks]
        assert codes.count("ar") == 1
        assert codes.count("en") == 2
        # Arabic is first overall because rating 60 > 20 > 10
        assert tracks[0].code == "ar"
        assert tracks[0].lang.startswith("العربية — Ar.DVDRip")
        assert tracks[0].url.endswith("/subtitle/mov-2.zip")

    def test_filters_unwanted_languages(self):
        html = _movie_html(
            _row(1, 50, "French", "mov-f", ["Fr.720p"]),
        )
        assert subs._parse_yify_movie(html, ["en"]) == []

    def test_per_lang_cap(self, monkeypatch):
        self._disable_cache(monkeypatch)
        rows = [_row(i, i * 10, "Arabic", f"mov-{i}", [f"Ar.{i}"]) for i in range(1, 6)]
        rows += [_row(i + 50, i * 10, "English", f"mov-en-{i}", [f"En.{i}"]) for i in range(1, 6)]
        resp_html = _movie_html(*rows)

        class FakeResp:
            text = resp_html

            def raise_for_status(self):
                pass

        class Client:
            def get(self, url):
                return FakeResp()

        @contextmanager
        def fake_client(**kwargs):
            yield Client()

        monkeypatch.setattr(subs, "new_http_client", fake_client)
        tracks = subs.fetch_yify("tt1375666", ["ar", "en"], per_lang=2)
        assert len(tracks) == 4
        assert sum(1 for t in tracks if t.code == "ar") == 2
        assert sum(1 for t in tracks if t.code == "en") == 2
        # highest rated per language kept; all 4 pass through in rating order
        assert [t.code for t in tracks] == ["ar", "en", "ar", "en"]

    def test_error_returns_empty(self, monkeypatch):
        def boom(*a, **kw):
            raise ConnectionError("net")

        monkeypatch.setattr(subs, "new_http_client", boom)
        assert subs.fetch_yify("tt1375666", ["en"]) == []

    def test_cache_avoids_network(self, monkeypatch):
        self._disable_cache(monkeypatch)
        # write a fake cache file
        html = _movie_html(_row(1, 42, "English", "mov-1", ["En.x264"]))
        raw = [subs._parse_yify_movie(html, ["en"])[0].model_dump()]
        cache_path = subs._cache_file("tt999", ["en"])
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(str(raw).replace("'", '"'))
        # monkeypatch get to always enable cache
        monkeypatch.setattr(subs, "get", lambda *a: True if a[1] == "enabled" else a[2])

        def should_not_be_called(*a, **kw):
            raise AssertionError("network should not be hit")

        monkeypatch.setattr(subs, "new_http_client", should_not_be_called)
        tracks = subs.fetch_yify("tt999", ["en"])
        assert len(tracks) == 1
        assert tracks[0].code == "en"


class TestSubsource:
    @staticmethod
    def _disable_cache(monkeypatch):
        monkeypatch.setattr(subs, "get", lambda *a: False if a[1] == "enabled" else a[2])

    @staticmethod
    def _page(*records: tuple[int, str, str, str]) -> str:
        parts = [
            (
                f'{{"id":{rid},"language":"{lang}","release_type":"other",'
                f'"release_info":"{release}","upload_date":"2024-01-01T00:00:00.000Z",'
                '"hearing_impaired":0,"caption":"","rating":"unrated","uploader_id":1,'
                f'"uploader_displayname":"u","link":"{link}","production_type":null,'
                '"last_subtitle":false}'
            )
            for rid, lang, release, link in records
        ]
        body = "[" + ",".join(parts) + "]"
        return f'<html><body><script>self.__next_f.push([1,"{body}"])</script></body></html>'

    @staticmethod
    def _slug_and_code():
        assert subs._subsource_slug("Breaking Bad") == "breaking-bad"
        assert subs._subsource_slug("Mr. Robot (2019)") == "mr-robot-2019"

    def test_code_mapping(self):
        assert subs._subsource_code("arabic") == "ar"
        assert subs._subsource_code("farsi_persian") == "fa"
        assert subs._subsource_code("big_5_code") == "zh"
        assert subs._subsource_code("brazilian_portuguese") == "pt"

    def test_parse_filters_by_episode(self):
        page = self._page(
            (
                454247,
                "arabic",
                "Breaking.Bad.S03E07.720p.HDTV.X264-DIMENSION",
                "breaking-bad-season-3/arabic/454247",
            ),
            (
                454248,
                "arabic",
                "Breaking.Bad.S03E08.720p.HDTV.X264-DIMENSION",
                "breaking-bad-season-3/arabic/454248",
            ),
            (
                454249,
                "english",
                "Breaking.Bad.S03E07.720p.HDTV.X264-DIMENSION",
                "breaking-bad-season-3/english/454249",
            ),
            (
                454250,
                "arabic",
                "Breaking.Bad.Season.03.720p-PFT",
                "breaking-bad-season-3/arabic/454250",
            ),
        )
        tracks = subs._parse_subsource_page(page, "breaking-bad-season-3", 3, 7, ["ar"])
        assert len(tracks) == 1  # season packs are rejected
        assert tracks[0].code == "ar"
        assert tracks[0].url.endswith("/subtitle/breaking-bad-season-3/arabic/454247")
        assert tracks[0].lang.startswith("العربية — Breaking.Bad.S03E07")

    def test_whole_season_packs_do_not_match_specific_episode(self, monkeypatch):
        self._disable_cache(monkeypatch)
        page = self._page(
            (
                1,
                "english",
                "Stargate.SG-1.S01.1080p.BluRay.x264-BORDURE",
                "stargate-sg-1-season-1/english/1",
            ),
            (2, "english", "Stargate.SG-1.S02.BluRay.REMUX", "stargate-sg-1-season-2/english/2"),
            (3, "english", "Stargate SG-1 Season 1", "stargate-sg-1-season-1/english/3"),
            (4, "english", "Stargate.SG-1.S01E02.720p", "stargate-sg-1-season-1/english/4"),
            (5, "english", "Stargate.SG-1.S01E03.720p", "stargate-sg-1-season-1/english/5"),
        )

        class Resp:
            status_code = 200
            text = page

            def raise_for_status(self):
                pass

        class Client:
            calls = []

            def get(self, url):
                Client.calls.append(url)
                return Resp()

        @contextmanager
        def fake_client(**kwargs):
            yield Client()

        monkeypatch.setattr(subs, "new_http_client", fake_client)
        tracks = subs.fetch_subsource("Stargate SG-1", ["en"], season=1, episode=2)
        # Only the exact S01E02 record is safe; season packs are rejected.
        assert len(tracks) == 1
        assert tracks[0].url.endswith("/4")

    def test_parse_filters_language(self):
        page = self._page(
            (1, "arabic", "Inception.2010.DVDRip", "inception-2010/arabic/1"),
            (2, "english", "Inception.2010.1080p", "inception-2010/english/2"),
        )
        tracks = subs._parse_subsource_page(page, "inception-2010", None, None, ["en"])
        assert len(tracks) == 1
        assert tracks[0].code == "en"

    def test_fetch_season_filter_and_cap(self, monkeypatch):
        self._disable_cache(monkeypatch)
        page = self._page(
            (1, "arabic", "Breaking.Bad.S03E01.720p", "breaking-bad-season-3/arabic/1"),
            (2, "arabic", "Breaking.Bad.S03E01.1080p", "breaking-bad-season-3/arabic/2"),
            (3, "arabic", "Breaking.Bad.S03E07.720p", "breaking-bad-season-3/arabic/3"),
            (4, "arabic", "Breaking.Bad.S03E07.1080p", "breaking-bad-season-3/arabic/4"),
            (5, "arabic", "Breaking.Bad.S03E07.2160p", "breaking-bad-season-3/arabic/5"),
        )

        class Resp:
            def __init__(self):
                self.status_code = 200
                self.text = page

            def raise_for_status(self):
                pass

        class Client:
            def get(self, url):
                assert url.endswith("/subtitles/breaking-bad/season-3")
                return Resp()

        @contextmanager
        def fake_client(**kwargs):
            yield Client()

        monkeypatch.setattr(subs, "new_http_client", fake_client)
        tracks = subs.fetch_subsource("Breaking Bad", ["ar"], season=3, episode=7, per_lang=2)
        assert len(tracks) == 2  # capped at 2 even though 3 candidates
        assert {t.url.rsplit("/", 1)[-1] for t in tracks} == {"3", "4"}

    def test_fetch_movie_slug_with_year(self, monkeypatch):
        self._disable_cache(monkeypatch)
        page = self._page(
            (1, "arabic", "Inception.2010.DVDRip", "inception-2010/arabic/1"),
        )

        class Resp:
            def __init__(self):
                self.status_code = 200
                self.text = page

            def raise_for_status(self):
                pass

        class Client:
            def get(self, url):
                assert url.endswith("/subtitles/inception-2010")
                return Resp()

        @contextmanager
        def fake_client(**kwargs):
            yield Client()

        monkeypatch.setattr(subs, "new_http_client", fake_client)
        tracks = subs.fetch_subsource("Inception", ["ar"], year=2010)
        assert len(tracks) == 1
        assert tracks[0].url.endswith("/inception-2010/arabic/1")

    def test_the_prefix_variant(self, monkeypatch):
        self._disable_cache(monkeypatch)
        page = self._page(
            (1, "english", "office.e01", "office/english/1"),
        )

        class Resp:
            def __init__(self, status, text):
                self.status_code = status
                self.text = text

            def raise_for_status(self):
                pass

        class Client:
            calls = []

            def get(self, url):
                Client.calls.append(url)
                if "the-office" in url:
                    return Resp(404, "")
                return Resp(200, page)

        @contextmanager
        def fake_client(**kwargs):
            yield Client()

        monkeypatch.setattr(subs, "new_http_client", fake_client)
        tracks = subs.fetch_subsource("The Office", ["en"])
        assert len(tracks) == 1
        assert any("the-office" in c for c in Client.calls)
        assert any(c.endswith("/subtitles/office") for c in Client.calls)

    def test_fetch_error_returns_empty(self, monkeypatch):
        self._disable_cache(monkeypatch)

        def boom(*a, **kw):
            raise ConnectionError("net")

        monkeypatch.setattr(subs, "new_http_client", boom)
        assert subs.fetch_subsource("Inception", ["en"]) == []

    def test_cache_avoids_network(self, monkeypatch):
        track = SubtitleTrack(
            lang="العربية — en.srt",
            code="ar",
            url="https://subsource.net/subtitle/x/arabic/1",
        )
        cache_path = subs._subsource_cache_file("inception", None, None, ["en"])
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(str([track.model_dump()]).replace("'", '"'))
        monkeypatch.setattr(
            subs,
            "get",
            lambda *a: True if a[1] == "enabled" else a[2],
        )

        def should_not_be_called(*a, **kw):
            raise AssertionError("network should not be hit")

        monkeypatch.setattr(subs, "new_http_client", should_not_be_called)
        assert subs.fetch_subsource("Inception", ["en"]) == [track]

    def test_download_two_step(self, tmp_path, monkeypatch):
        srt = ("1\n00:00:01,000 --> 00:00:03,000\nمرحبا\n").encode()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("Breaking.Bad.S03E07.720p.srt", srt)
        detail = (
            '<html><a href="https://api.subsource.net/v1/subtitle/download/'
            + "a" * 64
            + '">download</a></html>'
        )

        class Resp:
            def __init__(self, payload, is_text=True):
                self._payload = payload
                self._is_text = is_text
                self.status_code = 200

            def raise_for_status(self):
                pass

            @property
            def text(self):
                return self._payload if self._is_text else ""

            @property
            def content(self):
                return self._payload if not self._is_text else b""

        class Client:
            def get(self, url, headers=None):
                if url.startswith("https://api.subsource.net"):
                    return Resp(buf.getvalue(), is_text=False)
                return Resp(detail)

        @contextmanager
        def fake_client(**kwargs):
            yield Client()

        monkeypatch.setattr(subs, "new_http_client", fake_client)
        track = SubtitleTrack(
            lang="العربية — x",
            code="ar",
            url="https://subsource.net/subtitle/breaking-bad-season-3/arabic/454247",
        )
        path = download_subtitle(track, tmp_path)
        assert path == tmp_path / "ar.srt"
        content = path.read_bytes()
        assert "مرحبا".encode() in content


class TestFetchSubtitleFallback:
    class FakeUi:
        def subtitle_menu(self, tracks, title):
            return tracks[1]

    @staticmethod
    def _app(interactive: bool = True):
        ui = TestFetchSubtitleFallback.FakeUi()
        return type("App", (), {"_interactive": interactive, "ui": ui})()

    @staticmethod
    def _chosen() -> SearchResult:
        return SearchResult(imdb_id="tt1375666", title="Inception", media_type=MediaType.MOVIE)

    @staticmethod
    def _dest(*parts: str) -> str:
        return str(Path(cine.cache_dir()) / "subtitles" / Path(*parts))

    @staticmethod
    def _stub_download(monkeypatch):
        monkeypatch.setattr(
            cine,
            "download_subtitle",
            lambda t, dest: str(Path(dest) / f"{t.code or 'en'}.srt"),
        )

    @staticmethod
    def _auto(monkeypatch):
        monkeypatch.setattr(
            cine,
            "get",
            lambda section, key, default=None: (
                "auto" if (section, key) == ("subtitle", "source") else default
            ),
        )

    def test_auto_falls_back_when_provider_empty(self, monkeypatch):
        self._auto(monkeypatch)
        fetched = [SubtitleTrack(lang="English — En.srt", code="en", url="https://x.zip")]
        monkeypatch.setattr(cine, "fetch_yify", lambda imdb, lang: fetched)
        monkeypatch.setattr(cine, "fetch_subsource", lambda *a, **k: [])
        self._stub_download(monkeypatch)
        stream = StreamInfo(url="x", provider="fake", subtitles=[])
        out = cine.CineApp._fetch_subtitle(self._app(), stream, self._chosen())
        assert out == self._dest("tt1375666", "en.srt")

    def test_auto_keeps_provider_tracks(self, monkeypatch):
        self._auto(monkeypatch)
        provider_track = [SubtitleTrack(lang="eng", code="en", url="https://v/e.srt")]
        monkeypatch.setattr(cine, "fetch_yify", lambda imdb, lang: [])
        monkeypatch.setattr(cine, "fetch_subsource", lambda *a, **k: [])
        self._stub_download(monkeypatch)
        stream = StreamInfo(url="x", provider="fake", subtitles=provider_track)
        out = cine.CineApp._fetch_subtitle(self._app(), stream, self._chosen())
        assert out == self._dest("tt1375666", "en.srt")

    def test_candidate_exception_falls_through(self, monkeypatch):
        self._auto(monkeypatch)
        monkeypatch.setattr(cine, "fetch_yify", lambda *a, **k: [])
        monkeypatch.setattr(cine, "fetch_subsource", lambda *a, **k: [])
        tracks = [
            SubtitleTrack(lang="bad", code="en", url="https://bad"),
            SubtitleTrack(lang="good", code="ar", url="https://good"),
        ]

        class FakeUi:
            def subtitle_menu(self, tracks, title):
                return tracks[0]

        app = type("App", (), {"_interactive": True, "ui": FakeUi()})()
        calls = []

        def fake_download(track, dest):
            calls.append(track.url)
            if track.url == "https://bad":
                raise ValueError("bad subtitle")
            return str(Path(dest) / "ar.srt")

        monkeypatch.setattr(cine, "download_subtitle", fake_download)
        stream = StreamInfo(url="x", provider="fake", subtitles=tracks)
        out = cine.CineApp._fetch_subtitle(app, stream, self._chosen())
        assert calls == ["https://bad", "https://good"]
        assert out == self._dest("tt1375666", "ar.srt")

    def test_auto_merges_all_sources_and_dedupes(self, monkeypatch):
        provider_track = [SubtitleTrack(lang="en", code="en", url="https://v/e.srt")]
        yify_hit = [SubtitleTrack(lang="English — En.srt", code="en", url="https://v/e.srt")]
        subsource_hit = [SubtitleTrack(lang="العربية", code="ar", url="https://subsource.net/x")]
        os_hit = [SubtitleTrack(lang="English [HI] — 1x02", code="en", url="os:111")]
        monkeypatch.setattr(cine, "fetch_yify", lambda imdb, lang: yify_hit)
        monkeypatch.setattr(cine, "fetch_subsource", lambda title, lang, **kw: subsource_hit)
        monkeypatch.setattr(cine, "fetch_opensubtitles", lambda *a, **kw: os_hit)
        monkeypatch.setattr(
            cine,
            "get",
            lambda section, key, default=None: {
                ("opensubtitles", "api_key"): "KEY",
                ("opensubtitles", "username"): "user",
                ("opensubtitles", "password"): "pass",
            }.get((section, key), default),
        )
        captured = {}

        class CaptureUi(TestFetchSubtitleFallback.FakeUi):
            def subtitle_menu(self, tracks, title):
                captured["tracks"] = tracks
                return tracks[0]

        app = self._app()
        app.ui = CaptureUi()
        self._stub_download(monkeypatch)
        stream = StreamInfo(url="x", provider="fake", subtitles=provider_track)
        cine.CineApp._fetch_subtitle(app, stream, self._chosen())
        urls = [t.url for t in captured["tracks"]]
        assert urls == ["https://v/e.srt", "https://subsource.net/x", "os:111"]

    def test_provider_source_skips_yifysubtitles(self, monkeypatch):
        monkeypatch.setattr(
            cine,
            "get",
            lambda section, key, default=None: "provider" if key == "source" else default,
        )
        monkeypatch.setattr(
            cine,
            "fetch_yify",
            lambda imdb, lang: (_ for _ in ()).throw(AssertionError("not called")),
        )
        stream = StreamInfo(url="x", provider="fake", subtitles=[])
        assert cine.CineApp._fetch_subtitle(self._app(), stream, self._chosen()) is None

    def test_disabled_returns_none(self, monkeypatch):
        monkeypatch.setattr(cine, "get", lambda section, key, default=None: False)
        stream = StreamInfo(url="x", provider="fake", subtitles=[])
        assert cine.CineApp._fetch_subtitle(self._app(), stream, self._chosen()) is None

    def test_non_interactive_fetches_external_subtitles(self, monkeypatch):
        self._auto(monkeypatch)
        fetched = [SubtitleTrack(lang="English — En.srt", code="en", url="https://x.zip")]
        monkeypatch.setattr(cine, "fetch_yify", lambda imdb, lang: fetched)
        monkeypatch.setattr(cine, "fetch_subsource", lambda *a, **k: [])
        self._stub_download(monkeypatch)
        stream = StreamInfo(url="x", provider="fake", subtitles=[])
        out = cine.CineApp._fetch_subtitle(self._app(interactive=False), stream, self._chosen())
        assert out == self._dest("tt1375666", "en.srt")

    def test_picker_uses_menu_when_multiple_tracks(self, monkeypatch):
        self._auto(monkeypatch)
        tracks = [
            SubtitleTrack(lang="Arabic — ar.srt", code="ar", url="https://x/ar.zip"),
            SubtitleTrack(lang="English — en.srt", code="en", url="https://x/en.zip"),
        ]
        monkeypatch.setattr(cine, "fetch_yify", lambda imdb, lang: tracks)
        monkeypatch.setattr(cine, "fetch_subsource", lambda *a, **k: [])
        self._stub_download(monkeypatch)
        stream = StreamInfo(url="x", provider="fake", subtitles=[])
        out = cine.CineApp._fetch_subtitle(self._app(), stream, self._chosen())
        assert out == self._dest("tt1375666", "en.srt")

    def test_tv_uses_subsource_with_season_episode(self, monkeypatch):
        self._auto(monkeypatch)
        fetched = [
            SubtitleTrack(
                lang="العربية — Breaking.Bad.S03E01.720p",
                code="ar",
                url="https://subsource.net/subtitle/breaking-bad-season-3/arabic/454001",
            )
        ]
        seen = {}

        def fetch_cb(title, lang, **kw):
            seen.update(kw)
            return fetched

        monkeypatch.setattr(cine, "fetch_subsource", fetch_cb)
        monkeypatch.setattr(
            cine,
            "get",
            lambda section, key, default=None: (
                "auto" if (section, key) == ("subtitle", "source") else default
            ),
        )
        self._stub_download(monkeypatch)
        stream = StreamInfo(url="x", provider="fake", subtitles=[])
        chosen = SearchResult(imdb_id="tt0903747", title="Breaking Bad", media_type=MediaType.TV)
        out = cine.CineApp._fetch_subtitle(self._app(), stream, chosen, season=3, episode=1)
        assert seen == {"season": 3, "episode": 1}
        assert out == self._dest("tt0903747", "s03e01", "ar.srt")


class TestOpenSubtitles:
    KEY = "test_apikey"

    def _config(self, monkeypatch):
        monkeypatch.setattr(
            subs,
            "get",
            lambda *a: (
                self.KEY
                if a[:2] == ("opensubtitles", "api_key")
                else (
                    False
                    if a[:2] == ("cache", "enabled")
                    else (True if a[1] == "enabled" else a[2])
                )
            ),
        )

    def test_disabled_skips_even_with_key(self, monkeypatch):
        monkeypatch.setattr(
            subs,
            "get",
            lambda section, key, default=None: (
                self.KEY if key == "api_key" else (False if key == "enabled" else default)
            ),
        )
        assert subs.fetch_opensubtitles("tt0118480", ["en"]) == []

    def test_login_requires_username_and_password(self, monkeypatch):
        monkeypatch.setattr(
            subs,
            "get",
            lambda section, key, default=None: (
                self.KEY if key == "api_key" else (True if key == "enabled" else default)
            ),
        )
        monkeypatch.setattr(
            subs,
            "new_http_client",
            lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not login")),
        )
        assert subs._os_token() is None

    def test_login_posts_credentials_with_api_key_header(self, monkeypatch):
        monkeypatch.setattr(
            subs,
            "get",
            lambda section, key, default=None: {
                "api_key": self.KEY,
                "username": "user@example.com",
                "password": "secret",
                "enabled": True,
            }.get(key, default),
        )
        captured = {}

        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"token": "jwt"}

        class Client:
            def post(self, url, json=None):
                captured["url"] = url
                captured["json"] = json
                return Resp()

        @contextmanager
        def fake_client(**kwargs):
            captured["headers"] = kwargs.get("headers")
            yield Client()

        monkeypatch.setattr(subs, "new_http_client", fake_client)
        assert subs._os_token() == "jwt"
        assert captured["url"].endswith("/login")
        assert captured["json"] == {"username": "user@example.com", "password": "secret"}
        assert captured["headers"]["Api-Key"] == self.KEY

    def test_cached_token_is_bound_to_credentials(self, monkeypatch, tmp_path):
        creds = {"username": "one", "password": "first"}
        monkeypatch.setattr(
            subs,
            "get",
            lambda section, key, default=None: {
                "api_key": self.KEY,
                "enabled": True,
                **creds,
            }.get(key, default),
        )
        monkeypatch.setattr(subs, "cache_dir", lambda: tmp_path)
        calls = []

        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"token": "jwt"}

        class Client:
            def post(self, url, json=None):
                calls.append(json)
                return Resp()

        @contextmanager
        def fake_client(**kwargs):
            yield Client()

        monkeypatch.setattr(subs, "new_http_client", fake_client)
        assert subs._os_token() == "jwt"
        assert subs._os_token() == "jwt"
        assert len(calls) == 1
        creds["password"] = "second"
        assert subs._os_token() == "jwt"
        assert len(calls) == 2

    def test_no_api_key_skips(self, monkeypatch):
        monkeypatch.setattr(subs, "get", lambda *a: a[2])
        monkeypatch.setattr(
            subs,
            "_os_token",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not auth")),
        )
        assert subs.fetch_opensubtitles("tt0118480", ["en"]) == []

    def test_synthetic_imdb_id_skips_without_crashing(self, monkeypatch):
        self._config(monkeypatch)
        monkeypatch.setattr(
            subs,
            "new_http_client",
            lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not query")),
        )
        assert subs.fetch_opensubtitles("stardima:123", ["en"]) == []

    def test_token_file_is_private(self, monkeypatch, tmp_path):
        monkeypatch.setattr(subs, "cache_dir", lambda: tmp_path)
        subs._os_remember_token("secret")
        token_path = tmp_path / "os_token.json"
        assert token_path.exists()
        assert stat.S_IMODE(token_path.stat().st_mode) == 0o600

    def test_search_filters_langs_and_caps(self, monkeypatch):
        self._config(monkeypatch)
        payload = {
            "data": [
                {
                    "id": 1,
                    "attributes": {
                        "language": "en",
                        "release_name": "Show.S01E02.720p.WEB-DL",
                        "download_count": 10,
                        "hearing_impaired": False,
                        "files": [{"file_id": 111, "format": "srt"}],
                    },
                },
                {
                    "id": 2,
                    "attributes": {
                        "language": "ar",
                        "release_name": "Show.S01E02.ara",
                        "download_count": 5,
                        "files": [{"file_id": 222, "format": "srt"}],
                    },
                },
                {
                    "id": 3,
                    "attributes": {
                        "language": "fr",
                        "release_name": "French.One",
                        "download_count": 9,
                        "files": [{"file_id": 333, "format": "srt"}],
                    },
                },
                {
                    "id": 4,
                    "attributes": {
                        "language": "en",
                        "release_name": "Show.Second",
                        "download_count": 1,
                        "files": [{"file_id": 444, "format": "srt"}],
                    },
                },
            ]
        }
        captured = {}

        class Resp:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return payload

        class Client:
            def get(self, url, params=None):
                captured["url"] = url
                captured["params"] = params
                return Resp()

        @contextmanager
        def fake_client(**kwargs):
            yield Client()

        monkeypatch.setattr(subs, "new_http_client", fake_client)
        monkeypatch.setattr(subs, "_os_token", lambda *a, **k: "tok")
        tracks = subs.fetch_opensubtitles("tt0118480", ["en", "ar"], per_lang=1)
        assert captured["url"].endswith("/api/v1/subtitles")
        assert captured["params"]["imdb_id"] == "118480"  # tt prefix stripped
        assert "en,ar" in captured["params"]["languages"]
        assert len(tracks) == 2  # one per requested language
        assert tracks[0].code == "en"
        assert tracks[0].url == "os:111"
        assert "Show.S01E02.720p" in tracks[0].lang
        assert tracks[1].code == "ar"
        assert tracks[1].url == "os:222"

    def test_search_passes_season_episode(self, monkeypatch):
        self._config(monkeypatch)
        captured = {}

        class Resp:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"data": []}

        class Client:
            def get(self, url, params=None):
                captured["params"] = params
                return Resp()

        @contextmanager
        def fake_client(**kwargs):
            yield Client()

        monkeypatch.setattr(subs, "new_http_client", fake_client)
        monkeypatch.setattr(subs, "_os_token", lambda *a, **k: "tok")
        subs.fetch_opensubtitles("tt0118480", ["en"], season=1, episode=2)
        assert captured["params"]["season_number"] == "1"
        assert captured["params"]["episode_number"] == "2"

    def test_download_via_api_link(self, monkeypatch, tmp_path):
        self._config(monkeypatch)
        srt_body = gzip.compress(b"1\n00:00:00,000 --> 00:00:02,000\nHello\n\n")
        calls = {"post": 0}

        def post_resp():
            calls["post"] += 1
            return {"link": "https://dl/ok"}

        class Resp:
            status_code = 200
            content = srt_body

            def raise_for_status(self):
                pass

            def json(self):
                return post_resp()

        class Client:
            def post(self, url, json=None):
                return Resp()

            def get(self, url):
                return Resp()

        @contextmanager
        def fake_client(**kwargs):
            yield Client()

        monkeypatch.setattr(subs, "new_http_client", fake_client)
        monkeypatch.setattr(subs, "_os_token", lambda *a, **k: "tok")
        out = tmp_path / "ostest"
        path = subs._download_url(SubtitleTrack(lang="English", code="en", url="os:999"), out)
        assert path is not None
        assert path.exists()
        assert "Hello" in path.read_text()
        assert calls["post"] == 1

    def test_download_link_does_not_receive_api_auth(self, monkeypatch, tmp_path):
        self._config(monkeypatch)
        srt_body = gzip.compress(b"1\n00:00:00,000 --> 00:00:02,000\nHello\n\n")
        seen: list[dict[str, str]] = []

        class Resp:
            status_code = 200
            content = srt_body

            def raise_for_status(self):
                pass

            def json(self):
                return {"link": "https://dl.example/file.srt"}

        class Client:
            def post(self, url, json=None):
                return Resp()

            def get(self, url):
                return Resp()

        @contextmanager
        def fake_client(**kwargs):
            seen.append(dict(kwargs.get("headers") or {}))
            yield Client()

        monkeypatch.setattr(subs, "new_http_client", fake_client)
        monkeypatch.setattr(subs, "_os_token", lambda *a, **k: "tok")
        path = subs._download_url(SubtitleTrack(lang="English", code="en", url="os:999"), tmp_path)

        assert path is not None
        assert len(seen) == 2
        assert "Authorization" in seen[0]
        assert "Api-Key" in seen[0]
        assert "Authorization" not in seen[1]
        assert "Api-Key" not in seen[1]

    def test_download_retries_once_on_401(self, monkeypatch, tmp_path):
        self._config(monkeypatch)
        srt_body = gzip.compress(b"1\n00:00:00,000 --> 00:00:02,000\nHi\n\n")
        state = {"post": 0}

        class Resp:
            def __init__(self, status, content=b""):
                self.status_code = status
                self.content = content
                self._st = status

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise RuntimeError("http")

            def json(self):
                return {"link": "https://dl/x"}

        class Client:
            def post(self, url, json=None):
                state["post"] += 1
                if state["post"] == 1:
                    return Resp(401)
                return Resp(200, srt_body)

            def get(self, url):
                return Resp(200, srt_body)

        @contextmanager
        def fake_client(**kwargs):
            yield Client()

        monkeypatch.setattr(subs, "new_http_client", fake_client)
        monkeypatch.setattr(subs, "_os_token", lambda *a, **k: "tok")
        path = subs._download_url(
            SubtitleTrack(lang="English", code="en", url="os:999"), tmp_path / "ostest2"
        )
        assert path is not None
        assert state["post"] == 2  # 401 then retry


class TestSubtitleSafetyAndFormats:
    def _client(self, monkeypatch, content: bytes):
        class Resp:
            def raise_for_status(self):
                pass

        resp = Resp()
        resp.content = content

        class Client:
            def get(self, url):
                return resp

        @contextmanager
        def fake_client(**kwargs):
            yield Client()

        monkeypatch.setattr(subs, "new_http_client", fake_client)

    def test_ass_content_is_accepted_and_extension_corrected(self, tmp_path, monkeypatch):
        content = (
            b"[Script Info]\nTitle: x\n\n[Events]\n"
            b"Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hello\n"
        )
        self._client(monkeypatch, content)
        track = SubtitleTrack(lang="English", code="en", url="https://x/en.srt")

        path = download_subtitle(track, tmp_path)

        assert path == tmp_path / "en.ass"
        assert path.read_bytes() == content

    def test_code_cannot_escape_destination(self, tmp_path, monkeypatch):
        self._client(monkeypatch, b"1\n00:00:01,000 --> 00:00:02,000\nHi\n")
        track = SubtitleTrack(lang="English", code="../../evil", url="https://x/en.srt")

        path = download_subtitle(track, tmp_path)

        assert path is not None
        assert path.parent == tmp_path
        assert path.name == "evil.srt"

    def test_subsource_cache_distinguishes_movie_years(self):
        a = subs._subsource_cache_file("inception", None, None, ["en"], 2010)
        b = subs._subsource_cache_file("inception", None, None, ["en"], 2024)
        assert a != b
