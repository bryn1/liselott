"""T3.1 — Open Library client over the recorded fixture. The fixture was
recorded ONCE with the plan's exact curl and garbage-guarded
(docs>=1, "fixture garbage — re-record"); the first test re-asserts that
guard so an empty/error body can never bake in silently — the whole OL test
layer stands on it. The transport is the client's parameter: tests replay
fixtures, the live CLI uses app.enrich.http_get_json (ONE http mechanism)."""
import json
from pathlib import Path

import pytest

from app import enrich, enrich_ol

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "ol_stold.json"


def fixture_transport(payload):
    """Fixture-backed transport; hands out a fresh deep copy per call so a
    client that mutated a response could never poison the next request."""
    def get(url):
        assert isinstance(url, str) and url.startswith("https://")
        return json.loads(json.dumps(payload))
    return get


def test_fixture_holds_at_least_one_doc():
    docs = json.loads(FIXTURE.read_text(encoding="utf-8")).get("docs") or []
    assert len(docs) >= 1, "fixture garbage — re-record (T3.1 step 1)"


def test_stold_fixture_maps_isbn_year_cover():
    get = fixture_transport(json.loads(FIXTURE.read_text(encoding="utf-8")))
    hits = enrich_ol.search("Stöld", "Ann-Helén Laestadius", get_json=get)
    assert len(hits) == 1
    hit = hits[0]
    assert hit["title"] == "Stöld"
    assert hit["isbn13"] == "9789198559699"
    assert hit["year"] == 2022
    assert hit["cover_id"] == 14853286
    assert hit["cover_url"] == "https://covers.openlibrary.org/b/id/14853286-M.jpg"
    assert hit["authors"] == ["Ann-Helén Laestadius"]
    assert hit["source"] == "openlibrary"


def test_empty_docs_is_no_match_not_a_crash():
    get = fixture_transport({"numFound": 0, "docs": []})
    assert enrich_ol.search("Okänd bok", "Någon Författare", get_json=get) == []


def test_search_query_keeps_the_probe_shape():
    """The URL must carry the same searchable shape the plan probed live
    (title + author), the fields the mapping reads and the limit."""
    seen = []

    def get(url):
        seen.append(url)
        return {"docs": []}

    enrich_ol.search("Stöld", "Ann-Helén Laestadius", get_json=get)
    assert len(seen) == 1
    url = seen[0]
    assert url.startswith("https://openlibrary.org/search.json?")
    assert "title%3A%22St%C3%B6ld%22" in url          # title:"Stöld"
    assert "author%3A%22Ann-Hel%C3%A9n+Laestadius%22" in url
    assert "subject" in url                            # genres ride the same call


# ---- the ONE http helper (urllib, 3 s, retries, 429/5xx backoff) ----------

class FakeHTTPError(Exception):
    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.code = code


def test_http_get_retries_429_with_backoff_then_succeeds(monkeypatch):
    import urllib.error

    calls, sleeps = [], []

    class Flaky:
        def open(self, url, timeout=None):
            calls.append(timeout)
            if len(calls) < 3:
                raise urllib.error.HTTPError(url, 429, "Too Many Requests",
                                            None, None)
            class Body:
                def read(self, n=-1):
                    return b'{"docs": []}'

                def close(self):
                    pass
            return Body()

    data = enrich.http_get("https://example.test/x", opener=Flaky(),
                           sleep=sleeps.append)
    assert data == b'{"docs": []}'
    assert len(calls) == 3                 # attempt 1,2 fail; 3 succeeds
    assert all(t == 3.0 for t in calls)    # §T3.1: 3 s timeout per attempt
    assert sleeps == [pytest.approx(2.0), pytest.approx(4.0)]  # exponential


def test_http_get_gives_up_after_retries_raises_unavailable():
    import urllib.error

    class Broken:
        def open(self, url, timeout=None):
            raise urllib.error.URLError("no DNS")

    with pytest.raises(enrich.ProviderUnavailable):
        enrich.http_get("https://example.test/x", opener=Broken(),
                        sleep=lambda s: None, attempts=2)


def test_http_get_404_is_a_definitive_answer_not_retried():
    import urllib.error

    calls = []

    class NotThere:
        def open(self, url, timeout=None):
            calls.append(url)
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

    with pytest.raises(enrich.ProviderUnavailable):
        enrich.http_get("https://example.test/x", opener=NotThere(),
                        sleep=lambda s: None)
    assert len(calls) == 1     # definitive 4xx: no retry storm
