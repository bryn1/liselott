"""T3.2 — Google Books is OPPORTUNISTIC only (VERIFIED live: the no-key shared
consumer hard-429s today, §12). The client therefore carries a cooldown: a 429
writes settings.gb_cooldown_until = now + 6 h and every later call answers
available() False WITHOUT touching the transport; after the cooldown passes it
is asked again. The hit fixture is the documented volumes-API shape (live
record impossible while the API 429s from this host — SYNTHETIC, labelled in
the fixture file, same posture as the Libris fixture)."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import db, enrich, enrich_gb

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "gb_hit.json"


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    c = db.connect()
    db.init_db(c)
    yield c
    c.close()


def iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_hit_fixture_maps_isbn_year_thumbnail():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    hit = enrich_gb.map_volume(payload["items"][0])
    assert hit["isbn13"] == "9789198559699"
    assert hit["isbn10"] == "9198559699"
    assert hit["year"] == 2022
    assert hit["thumbnail"].startswith("https://books.google.com/books/content")
    assert hit["source"] == "googlebooks"


def test_search_over_fixture_transport(conn):
    calls = []

    def get(url, **kw):
        calls.append(url)
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    hits = enrich_gb.search("Stöld", "Ann-Helén Laestadius", conn, get_json=get)
    assert hits and hits[0]["isbn13"] == "9789198559699"
    assert calls[0].startswith("https://www.googleapis.com/books/v1/volumes?")
    assert "intitle" in calls[0] and "inauthor" in calls[0]
    assert "St%C3%B6ld" in calls[0]          # Swedish chars travel encoded


def test_429_sets_six_hour_cooldown_and_returns_none(conn):
    def flaky(url, **kw):
        raise enrich.RateLimited("429 from https://www.googleapis.com/...")

    NOW = 1_750_000_000.0
    assert enrich_gb.search("Stöld", "Laestadius", conn,
                            get_json=flaky, now=lambda: NOW) is None
    until = db_get(conn, "gb_cooldown_until")
    assert until == iso(NOW + 6 * 3600)


def test_while_cooling_down_the_transport_is_never_called(conn):
    NOW = [1_750_000_000.0]
    calls = []

    def get(url, **kw):
        calls.append(url)
        return {"totalItems": 0, "items": []}

    enrich_gb.set_cooldown(conn, NOW[0] + 6 * 3600)
    assert enrich_gb.available(conn, now=lambda: NOW[0]) is False
    assert enrich_gb.search("S", "A", conn, get_json=get,
                            now=lambda: NOW[0]) is None
    assert calls == []                       # transport untouched (§T3.2)

    # and it re-opens the instant the cooldown passes (no second mechanism):
    NOW[0] += 6 * 3600 + 1
    assert enrich_gb.available(conn, now=lambda: NOW[0]) is True
    assert enrich_gb.search("S", "A", conn, get_json=get,
                            now=lambda: NOW[0]) == []   # asked again: answered nothing
    assert len(calls) == 1


def test_answered_nothing_is_the_empty_list_not_the_unavailable_none(conn):
    def empty(url, **kw):
        return {"totalItems": 0, "items": []}

    assert enrich_gb.search("S", "A", conn, get_json=empty,
                            now=lambda: 1.0) == []


def test_a_non_429_failure_never_sets_the_cooldown(conn):
    def broken(url, **kw):
        raise enrich.ProviderUnavailable("transport failed")

    assert enrich_gb.search("S", "A", conn, get_json=broken,
                            now=lambda: 1.0) is None
    assert db_get(conn, "gb_cooldown_until") is None
    assert enrich_gb.available(conn, now=lambda: 1.0) is True


def db_get(conn, key):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None
