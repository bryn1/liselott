"""MC 12497 — the public-read per-route matrix (owner ruling 2026-11-14,
verbatim): "The website sibbamala.com/liselott should be public. All rate
books should be public. Rating and whishing is blocked behind liselotts
password" => reading is public, writing is private.

The matrix the DoD pins, on a CONFIGURED scratch state (the synthetic
shelf from tests/test_browse — corpus-free, so this file runs in any
clone):

* every read route — /, /bibliotek, /bok/<id>, /sok, /rekommendationer,
  /cover/<id> — answers 200 to an ANONYMOUS client, with the real page on
  the body (a starred rating, a hit, cover bytes: something only the data
  route can answer with);
* every write route refuses an anonymous POST non-2xx (the guard's 302 —
  the route contract's refuse), including POSTs aimed at READ paths: the
  method check in _is_public_read is what makes "public to read" not mean
  "public to write";
* no anonymous read ever sets a session cookie, and no public page paints
  an owner door (edit page, add page, byt lösenord, logga ut, the betyg
  widget, "Visa inte igen");
* the SETUP-STATE exception: while no password is set the choose-password
  gate still wraps the whole site — every data route (public or owner)
  redirects to /satt-loesenord, and the root lands the setup door;
* the authenticated owner still reads AND writes end-to-end (the grading
  write flips the row and the public page then SHOWS the new rating — the
  one leg that proves read-public and write-private are the same app).

The quarantine legs (state files 404 in every state) stay in test_guard;
the corpus leak matrix under this same contract is test_no_leak.
"""
import sqlite3

import pytest

from app import create_app
from tests.test_browse import PASSWORD, seed_shelf

# (method, path, expected refuse) — the full write surface of the app.
# /satt-loesenord refuses as 404 because a configured site retires it (§6.1),
# everything else takes the guard's uniform 302 to the login page.
WRITE_ROUTES = [
    ("/betyg/1", 302), ("/onska/lagg-till", 302), ("/onska/5/las", 302),
    ("/redigera/1", 302), ("/ta-bort/1", 302), ("/lagg-till", 302),
    ("/djem/book/1", 302), ("/omslag/1", 302), ("/omslag/1/hitta", 302),
    ("/omslag/1/ladda-up", 302), ("/byter-losenord", 302),
    ("/seed", 302), ("/bundle", 302), ("/backfill", 302),
    ("/satt-loesenord", 404),
    # writes aimed at READ paths — the matrix's sharp corner:
    ("/", 302), ("/bibliotek", 302), ("/bok/1", 302), ("/sok", 302),
    ("/rekommendationer", 302), ("/cover/1", 302),
]


def _app():
    app = create_app()
    app.testing = True
    return app


@pytest.fixture()
def configured(tmp_path, monkeypatch):
    """The synthetic shelf + the password set — the CONFIGURED state the
    public-read contract is a property of."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    (tmp_path / "covers").mkdir()
    (tmp_path / "covers/2.jpg").write_bytes(b"\xff\xd8\xff Synthetic 2")
    app = _app()
    client = app.test_client()
    assert client.post("/liselott/satt-loesenord",
                       data={"loesenord": PASSWORD,
                             "bekrafta": PASSWORD}).status_code == 302
    return tmp_path, client


@pytest.fixture()
def fresh(tmp_path, monkeypatch):
    """No password set, window open: the setup-state exception's stage."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    app = _app()
    return tmp_path, app.test_client()


# ── configured state: reads public, with real data on the body ──────────────
def test_read_routes_answer_anonymous_with_their_data(configured):
    _, client = configured
    anon = _app().test_client()                     # same state, no session

    r = anon.get("/liselott/bibliotek")
    assert r.status_code == 200
    for title in ("Stöld", "God jul Agnes", "En bur av guld"):
        assert title in r.text                  # "Att läsa" is on there too
    assert 'aria-label="Betyg 4 av 5"' in r.text  # the stars READ public

    r = anon.get("/liselott/bok/2")
    assert r.status_code == 200
    assert "Stöld" in r.text and "Ann-Helén Laestadius" in r.text
    r = anon.get("/liselott/bok/1")             # the note ships with the page
    assert r.status_code == 200
    assert "Sommarstugeklassikern" in r.text

    r = anon.get("/liselott/sok", query_string={"q": "Stöld"})
    assert r.status_code == 200 and "Stöld" in r.text

    r = anon.get("/liselott/rekommendationer")
    assert r.status_code == 200                 # the rec surface, §8 page

    r = anon.get("/liselott/cover/2")           # the stored cover, real bytes
    assert r.status_code == 200 and r.mimetype == "image/jpeg"
    r = anon.get("/liselott/cover/1")           # no cover: the honest SVG
    assert r.status_code == 200 and r.mimetype == "image/svg+xml"

    r = anon.get("/liselott/")                  # the landing leg stays a landing
    assert r.status_code == 200
    assert "Din hylla" not in r.text


def test_write_routes_refuse_anonymous(configured):
    _, _ = configured
    anon = _app().test_client()
    for path, refuse in WRITE_ROUTES:
        r = anon.post(path, data={"x": "1"})
        assert r.status_code == refuse, (path, r.status_code)
        if refuse == 302:                       # the guard's uniform refuse
            assert r.headers["Location"] == "/liselott/logga-in", path
        assert not (200 <= r.status_code < 300), path   # never a 2xx write


# ── configured state: what the public pages may NOT carry ───────────────────
def test_anonymous_reads_set_no_session_cookie(configured):
    _, _ = configured
    anon = _app().test_client()
    for path in ("/liselott/", "/liselott/bibliotek", "/liselott/bok/1",
                 "/liselott/sok?q=Stöld", "/liselott/rekommendationer",
                 "/liselott/cover/1"):
        r = anon.get(path)
        assert "Set-Cookie" not in r.headers, path


def test_public_pages_paint_no_owner_door(configured):
    _, _ = configured
    anon = _app().test_client()
    for path in ("/liselott/", "/liselott/bibliotek", "/liselott/bok/1",
                 "/liselott/bok/2", "/liselott/rekommendationer"):
        html = anon.get(path).text
        for door in ("/redigera/", "/byter-losenord", "/lagg-till",
                     "/logga-ut", "/ta-bort/", "/onska/lagg-till",
                     "Spara betyg", "Visa inte igen", "Omslag saknas"):
            assert door not in html, (path, door)


def test_public_book_page_still_shows_the_readonly_stars(configured):
    """The flip must not overshoot: hiding the WRITE widget may not hide the
    READ fact — book 2 carries rating 4 and the anon page must paint it."""
    _, _ = configured
    anon = _app().test_client()
    assert 'aria-label="Betyg 4 av 5"' in anon.get("/liselott/bok/2").text


# ── the setup-state exception: no password -> nothing is public ─────────────
def test_fresh_state_wraps_the_whole_site(fresh):
    _, client = fresh
    anon = _app().test_client()
    assert client.get("/liselott/satt-loesenord").status_code == 200  # open
    for path in ("/bibliotek", "/bok/1", "/bok/2", "/sok?q=x",
                 "/rekommendationer", "/cover/1", "/onska", "/lagg-till"):
        r = anon.get("/liselott" + path)
        assert r.status_code == 302, path
        assert r.headers["Location"] == "/liselott/satt-loesenord", path
        assert "Stöld" not in r.text, path       # a redirect carries no data
    assert anon.post("/liselott/betyg/1",
                     data={"betyg": "5"}).status_code == 302
    root = anon.get("/liselott/")                # the landing leg as pinned
    assert root.status_code == 200
    assert "Välj ditt lösenord" in root.text


# ── the owner still reads AND writes end-to-end ─────────────────────────────
def test_owner_read_and_write_still_work_end_to_end(configured):
    tmp, client = configured
    r = client.get("/liselott/bibliotek")        # read: her shelf, header on
    assert r.status_code == 200
    assert 'href="/liselott/logga-ut"' in r.text
    with client.session_transaction("/liselott/logga-in") as sess:
        tok = sess["csrf"]
    r = client.post("/liselott/betyg/3",
                    data={"betyg": "5", "csrf": tok})   # write: grade a book
    assert r.status_code == 302
    conn = sqlite3.connect(tmp / "liselott.db")
    assert conn.execute("SELECT rating FROM book WHERE id = 3",
                        ()).fetchone()[0] == 5
    conn.close()
    # the flip lands in the PUBLIC render: the anon page now shows 5 stars
    anon = _app().test_client()
    assert 'aria-label="Betyg 5 av 5"' in anon.get("/liselott/bok/3").text
    # and the owner's edit doors paint on HER pages (not on anon's)
    assert "Omslag saknas — fixa" in client.get("/liselott/bok/1").text
