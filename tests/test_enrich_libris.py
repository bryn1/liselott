"""T3.3 — the Libris client, re-pointed to the host that actually answers.

PLAN-c3 §12 pinned `librisxl.net` and measured NO-DNS for it; the measurement
was right and the host was wrong (`libris.kb.se` answers), so the owner of the
run ruled the correction on 2026-11-13. What this file proves is unchanged in
kind: the client degrades silently (a transport failure marks it DOWN for 10
minutes and no exception ever reaches a row), and it parses the REAL response
shape — because the fixtures are now RECORDED live responses from
libris.kb.se (2026-11-13), not synthetic documents. The synthetic pair that
stood here while the host was assumed dead is deleted.

Tests are OFFLINE: they replay the recorded files through an injected
`get_json`; nothing here touches the network. Production runs on the module's
shared DEFAULT instance, which is what the CLI and the /backfill route both use
(one mechanism, P2-b)."""
import json
from pathlib import Path

import pytest

from app import enrich, enrich_libris

FIXTURES = Path(__file__).resolve().parent / "fixtures"
STOLD = FIXTURES / "libris_xsearch_stold.json"
PIANISTEN = FIXTURES / "libris_xsearch_den-sarade-pianisten.json"
AGNES = FIXTURES / "libris_xsearch_god-jul-agnes.json"
NO_HIT = FIXTURES / "libris_xsearch_helenas-resa.json"
RECORD = FIXTURES / "libris_record_19738367.json"
RECORD_NO_IMAGE = FIXTURES / "libris_record_19257852.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture()
def lib():
    return enrich_libris.Libris()


def test_fixtures_are_recorded_live_responses_not_synthetic_documents():
    """The old guard asserted a SYNTHETIC marker; after the host correction a
    synthetic Libris fixture would be a lie. These files carry the API's own
    envelope and no marker of either kind."""
    for path in (STOLD, PIANISTEN, AGNES, NO_HIT, RECORD, RECORD_NO_IMAGE):
        payload = load(path)
        assert "_comment" not in payload, path
    assert load(STOLD)["xsearch"]["records"] == 81          # what the API said
    assert load(NO_HIT)["xsearch"]["records"] == 0


def test_find_url_is_free_text_and_carries_no_fieled_syntax(lib):
    """Measured: `titel:"…" AND creators:"…"` answers 0 records, the plain
    form finds the book — the plan's pinned syntax is not this API's."""
    url = lib.build_find_url("Stöld", "Ann-Helén Laestadius")
    assert url.startswith("https://libris.kb.se/xsearch?") and "format=json" in url
    assert "St%C3%B6ld+Ann-Hel%C3%A9n+Laestadius" in url
    assert "titel" not in url and "creators" not in url
    assert lib.build_find_url("Stöld", "").endswith("query=St%C3%B6ld")


def test_map_find_reads_the_recorded_page_and_normalizes_libris_names(lib):
    """`creator` is Libris' inverted 'Surname, First, 1971-'; left as-is it
    would sit in the way of the author gate, so it comes out as a given name
    first and without the life span."""
    hits = lib.map_find(load(STOLD))
    assert len(hits) == 10                       # the page the API chose to send
    assert hits[0]["title"] == "16. Ann-Helén Laestadius: Stöld"   # noise, first
    assert hits[0]["isbn13"] is None
    real = next(h for h in hits if h["isbn13"] == "9789198559699")
    assert real["title"] == "Stöld" and real["year"] == 2022
    assert real["authors"] == ["Ann-Helén Laestadius"]
    assert real["source"] == "libris" and real["type"] == "book"
    assert lib.map_find(load(AGNES))[0]["authors"] == ["Kristin Emilsson"]


def test_map_find_caps_at_one_page_and_survives_an_empty_answer(lib):
    assert len(lib.map_find(load(PIANISTEN))) == 8
    assert lib.map_find(load(NO_HIT)) == []      # answered: nothing found
    assert lib.map_find(None) == []


def test_year_survives_bibliographic_date_strings(lib):
    """'cop. 2016', '[2017]', 'p 2016', '2015)' — a naive first-four-chars read
    finds no year in any of them."""
    assert lib.map_find({"xsearch": {"list": [{"title": "x", "date": ["cop. 2016"]}]}}
                        )[0]["year"] == 2016
    assert lib.map_find({"xsearch": {"list": [{"title": "x", "date": "[2017]"}]}}
                        )[0]["year"] == 2017
    assert lib.map_find({"xsearch": {"list": [{"title": "x", "date": ["2015)"]}]}}
                        )[0]["year"] == 2015
    assert lib.map_find({"xsearch": {"list": [{"title": "x", "date": "okänt"}]}}
                        )[0]["year"] is None


def test_get_url_only_exists_for_the_ids_that_have_a_json_form(lib):
    """Newer hashed production ids answer 404 on EVERY json form measured, so
    no request is made for them at all — the find fields are the answer."""
    assert lib.build_get_url("http://libris.kb.se/bib/19738367") == \
        "https://libris.kb.se/resource/bib/19738367"
    assert lib.build_get_url("http://libris.kb.se/bib/f01ntzjqcskkwsqg") is None
    assert lib.build_get_url(None) is None


def test_map_doc_reads_subjects_authors_and_the_largest_fitting_cover(lib):
    doc = lib.map_doc(load(RECORD))
    assert doc["title"] == "Den sårade pianisten"
    assert doc["authors"] == ["Maria Ernestam"]          # givenName+familyName
    assert doc["isbn13"] == "9789175036267" and doc["year"] == 2017
    assert "Efterforskningar" in doc["subjects"] and "Hemligheter" in doc["subjects"]
    # the record offers 128/256 thumbnails and a 1400×2265 original: pulling the
    # original for a ≤340×510 cover is waste, so the largest THAT FITS wins
    assert doc["cover_url"] == ("https://libris.kb.se/dataset/images/"
                                "cf33661d638faef312baa150a8f1c671.256.jpg")
    assert lib.map_doc({}) == {}


def test_a_ljudbok_record_keeps_authors_and_labels_from_a_different_shape(lib):
    """The second real record is an audiobook: `role` answers as a LIST, one
    contribution carries no role at all (PrimaryContribution = the author), the
    narrator must not be read as an author, and subjects use `label` where the
    other record used `prefLabel`. It has no image — cover_url stays None."""
    doc = lib.map_doc(load(RECORD_NO_IMAGE))
    assert doc["authors"] == ["Maria Ernestam"]
    assert "Kvinnoskildringar" in doc["subjects"]
    assert doc["year"] == 2016
    assert doc["cover_url"] is None


def test_find_then_record_composes_one_hit(lib):
    calls = []

    def get(url, **kw):
        calls.append(url)
        if "resource/bib" in url:
            return load(RECORD)
        return load(PIANISTEN)

    hits = lib.search("Den sårade pianisten", "Maria Ernestam", get_json=get)
    hit = next(h for h in hits if h["id"].endswith("19738367"))
    assert hit["subjects"] and hit["cover_url"].endswith(".256.jpg")
    assert any("resource/bib/19738367" in url for url in calls)
    # a hashed id in the same page must NOT be requested (no JSON form exists)
    assert not any("f01ntzjqcskkwsqg" in url for url in calls)


def test_a_record_that_fails_leaves_the_find_fields_and_is_not_a_down_mark(lib):
    """404 on a hashed/legacy id is a definite answer, not an unavailability —
    marking DOWN here would blind the client for 10 minutes over one record."""
    def get(url, **kw):
        if "resource/bib" in url:
            raise enrich.ProviderUnavailable("404")
        return load(AGNES)

    hits = lib.search("God jul Agnes", "Kristin Emilsson", get_json=get)
    assert hits and hits[0]["isbn13"] == "9789181052237"
    assert hits[0]["subjects"] == [] and hits[0]["cover_url"] is None
    assert lib.available() is True


def test_a_find_failure_marks_down_and_swallows_everything(lib):
    now = [1000.0]
    clock = lambda: now[0]
    calls = []

    def get(url, **kw):
        calls.append(url)
        raise enrich.ProviderUnavailable("nommer")

    assert lib.search("Stöld", "Laestadius", get_json=get, now=clock) is None
    assert calls and lib.available(now=clock) is False
    # inside the window: no call at all, and still no exception
    assert lib.search("Stöld", "Laestadius", get_json=get, now=clock) is None
    assert len(calls) == 1
    now[0] += lib.DOWN_S + 1
    assert lib.available(now=clock) is True
    # after the window the client dials out again, and a live answer sticks
    now[0] += 1
    assert lib.search("Stöld", "Laestadius",
                      get_json=lambda url, **kw: load(STOLD), now=clock)
    assert lib.available(now=clock) is True


def test_the_json_opener_sends_the_accept_header_the_records_require():
    """Without Accept the endpoint answers text/html (verified live), so the
    header is part of the client — and it rides the SAME opener as every other
    provider call: same UA, timeout, retries and byte cap."""
    opener = enrich_libris.json_opener()
    handler = [h for h in opener.handlers
               if isinstance(h, enrich_libris._AcceptJSON)]
    assert handler, "the Accept handler is not on the opener"
    request = __import__("urllib.request", fromlist=["Request"]).Request(
        "https://libris.kb.se/resource/bib/19738367")
    assert handler[0].http_request(request).get_header("Accept") == "application/json"
