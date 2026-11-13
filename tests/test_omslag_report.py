"""T5.5 — the F-2 loop's instrument: what covers exist, what is missing, and
which rows are VERIFIED-unobtainable (never a fake cover, the honest residue).

The JSON contract is the plan's verbatim: total/with_cover/missing/manual +
the `unobtainable` rows — enrich_fail=1 AND tried_providers covering all THREE
provider names (the M3 evidence columns exist exactly so this is answerable);
the HTML page lists the missing with per-row buttons: retry through THE
provider door (/omslag/<id>), a bare ISBN input posting to THE edit door
(/redigera/<id> — per-field semantics make a one-field post safe, T5.2), and a
link to the upload door.

NEW /rapa/rekommendation-rapport is the P1-4 acceptance instrument:
{"rated": r, "candidates": c, "pool_nonempty": c>0}."""
import sqlite3

import pytest

from app import create_app
from tests.test_browse import PASSWORD, seed_shelf


@pytest.fixture()
def shelf(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    conn = sqlite3.connect(tmp_path / "liselott.db")
    now = "2026-11-13T00:00:00Z"
    # book 1: asked everybody, got nothing — the VERIFIED-unobtainable case
    conn.execute("UPDATE book SET enrich_fail = 1,"
                 " tried_providers = 'libris,ol,gb' WHERE id = 1")
    # book 3: tried libris+ol only — MISSING but not yet unobtainable
    conn.execute("UPDATE book SET enrich_fail = 1,"
                 " tried_providers = 'libris,ol' WHERE id = 3")
    # book 4: an admin's own cover — counted as manual
    conn.execute("UPDATE book SET cover_path = 'covers/4.jpg',"
                 " cover_source = 'manual' WHERE id = 4")
    conn.commit()
    conn.close()
    app = create_app()
    app.testing = True
    client = app.test_client()
    assert client.post("/liselott/satt-loesenord",
                       data={"loesenord": PASSWORD, "bekrafta": PASSWORD}).status_code == 302
    return tmp_path, client


def test_omslag_rapport_json_shape_and_counts(shelf):
    client = shelf[1]
    r = client.get("/liselott/rapa/omslag-rapport")
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("application/json")
    rep = r.get_json()
    assert rep["total"] == 5
    assert rep["with_cover"] == 2                 # book 2 (ol) + book 4 (manual)
    assert rep["missing"] == 3                    # books 1, 3, 5
    assert rep["manual"] == 1
    got = rep["unobtainable"]
    assert [u["id"] for u in got] == [1]          # only the all-THREE-names row
    assert got[0]["title"] == "God jul Agnes"
    assert got[0]["tried_providers"] == "libris,ol,gb"


def test_html_page_lists_missing_with_the_three_real_doors(shelf):
    client = shelf[1]
    page = client.get("/liselott/rapa/omslag")
    assert page.status_code == 200
    assert "God jul Agnes" in page.text           # missing rows listed
    assert "Vår i Fågelkärr" in page.text
    assert "Stöld" not in page.text               # has a cover — NOT listed
    # per-row doors, all url_for-shaped:
    assert 'action="/liselott/omslag/1"' in page.text        # retry (provider)
    assert 'action="/liselott/redigera/1"' in page.text      # ISBN input (edit door)
    assert 'name="isbn13"' in page.text
    assert 'href="/liselott/redigera/1"' in page.text        # upload link
    # and the honest mark on the unobtainable row
    assert "försökte" in page.text.lower()


def test_rapport_ignores_wishlist_status(shelf):
    """The report is about covers, not status — the wish (book 5) is missing a
    cover and belongs in the count."""
    rep = shelf[1].get("/liselott/rapa/omslag-rapport").get_json()
    assert 5 in [b for b in (1, 3, 5)] and rep["missing"] == 3


def test_rekommendation_rapport_is_the_p1_4_instrument(shelf):
    tmp, client = shelf
    r = client.get("/liselott/rapa/rekommendation-rapport")
    assert r.status_code == 200
    rep = r.get_json()
    assert rep["rated"] == 3                       # books 1,2,4 carry ratings
    assert rep["candidates"] == 0
    assert rep["pool_nonempty"] is False
    conn = sqlite3.connect(tmp / "liselott.db")
    conn.execute("INSERT INTO candidate (title, author_name, fetched_at)"
                 " VALUES ('K', 'A', '2026-11-13T00:00:00Z')")
    conn.commit()
    conn.close()
    rep = client.get("/liselott/rapa/rekommendation-rapport").get_json()
    assert rep["candidates"] == 1 and rep["pool_nonempty"] is True


def test_both_rapporter_are_behind_the_guard(shelf):
    fresh = shelf[1].application.test_client()
    for path in ("/liselott/rapa/omslag", "/liselott/rapa/omslag-rapport",
                 "/liselott/rapa/rekommendation-rapport"):
        r = fresh.get(path)
        assert r.status_code == 302, path
        assert r.headers["Location"] == "/liselott/logga-in", path
