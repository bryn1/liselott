"""T3.3 — Libris client: ships per owner requirement, but the VERIFIED VM350
reality is NO-DNS (both domains), so the client must degrade silently: a
transport failure marks the provider DOWN for 10 minutes (§12 availability
cache) and every later call in that window answers available() False WITHOUT
touching the transport; no exception ever escapes into a row. The fixtures are
SYNTHETIC (labelled in-file) — the API is unreachable from the build clone, so
no live recording exists; the client parses THIS documented shape.

Tests drive their OWN Libris() instances (explicit state, no order coupling);
production runs on the module's shared DEFAULT instance, which is what the CLI
and the /backfill route both use (one mechanism, P2-b)."""
import json
from pathlib import Path

import pytest

from app import enrich, enrich_libris

FIND_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "libris_find.json"
GET_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "libris_get.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture()
def lib():
    return enrich_libris.Libris()


def test_fixture_files_parse_as_json_and_are_labelled_synthetic():
    for path in (FIND_FIXTURE, GET_FIXTURE):
        payload = load(path)
        assert payload.get("_comment", "").startswith("SYNTHETIC"), path


def test_find_fixture_parses_the_first_doc(lib):
    hits = lib.map_find(load(FIND_FIXTURE))
    assert len(hits) == 1
    hit = hits[0]
    assert hit["id"] == "librisdoc:b123456789012001"
    assert hit["isbn13"] == "9789198559699"
    assert hit["year"] == 2022
    assert hit["title"] == "Stöld"
    assert hit["source"] == "libris"


def test_find_then_get_composes_one_hit(lib):
    calls = []

    def get(url, **kw):
        calls.append(url)
        return load(GET_FIXTURE) if "get.json" in url else load(FIND_FIXTURE)

    hits = lib.search("Stöld", "Ann-Helén Laestadius", get_json=get)
    assert len(hits) == 1
    hit = hits[0]
    assert hit["isbn13"] == "9789198559699"
    assert hit["subjects"] == ["Skönlitteratur", "Romaner"]
    assert hit["authors"] == ["Ann-Helén Laestadius"]
    # find.json first, then get.json for the doc — the plan's two-call design
    assert "find.json" in calls[0] and "get.json" in calls[1]
    assert "titel%3A%22St%C3%B6ld%22" in calls[0]     # the plan's query shape
    assert "creators" in calls[0]


def test_unreachable_provider_is_marked_down_for_ten_minutes(lib):
    calls = []

    def broken(url, **kw):
        calls.append(url)
        raise enrich.ProviderUnavailable("transport failed")  # VM350: NO-DNS

    now = [1_000.0]
    clock = lambda: now[0]

    assert lib.available(now=clock) is True
    assert lib.search("S", "A", get_json=broken, now=clock) is None
    assert lib.available(now=clock) is False              # DOWN for 10 min

    now[0] += 600 - 1
    assert lib.available(now=clock) is False              # still cooling
    assert lib.search("S", "A", get_json=broken, now=clock) is None
    assert len(calls) == 1                                # never re-asked

    now[0] += 2
    assert lib.available(now=clock) is True               # window passed
    assert lib.search("S", "A", get_json=broken, now=clock) is None
    assert len(calls) == 2                                # one fresh attempt


def test_a_later_success_clears_the_down_mark(lib):
    """The cache ages out on its own — the provider is asked again, and a
    success resets the availability state."""
    now = [0.0]
    clock = lambda: now[0]

    def flaky(url, **kw):
        if now[0] < 700:
            raise enrich.ProviderUnavailable("no DNS")
        return load(FIND_FIXTURE) if "find.json" in url else load(GET_FIXTURE)

    assert lib.search("Stöld", "Laestadius", get_json=flaky, now=clock) is None
    now[0] = 700.0
    hits = lib.search("Stöld", "Laestadius", get_json=flaky, now=clock)
    assert len(hits) == 1
    assert lib.available(now=clock) is True


def test_no_match_is_the_empty_list_not_none(lib):
    def empty(url, **kw):
        return {"hits": {"docs": []}}

    assert lib.search("S", "A", get_json=empty, now=lambda: 1.0) == []


def test_get_json_failure_falls_back_to_the_find_doc(lib):
    """get.json is the enrichment step; if it fails the find-doc fields still
    stand — a partial answer beats no answer."""
    def get(url, **kw):
        if "get.json" in url:
            raise enrich.ProviderUnavailable("get.json down")
        return load(FIND_FIXTURE)

    hits = lib.search("Stöld", "Laestadius", get_json=get, now=lambda: 1.0)
    assert len(hits) == 1
    assert hits[0]["isbn13"] == "9789198559699"
    assert hits[0]["subjects"] == []
