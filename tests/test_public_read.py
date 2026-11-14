"""MC 12501 — the public-SCOPE per-route matrix (owner ruling 2026-11-14,
web chat, verbatim): "Rated books and their ratings as well as whishlist
shall be public. The rest behind password".

This SUPERSEDES the same-day broader read of MC 12497 ("The website ...
should be public") — the newer ruling binds; the older quote stands on that
card's trail, not as the contract any more. The PUBLIC SET is the books the
owner RATED (rating IS NOT NULL) plus the wishlist rows — one predicate,
books.PUBLIC_SET_SQL. The matrix this file pins on a CONFIGURED scratch
state (the synthetic shelf from tests/test_browse plus one extra row, see
_the_private_only_year below — corpus-free, so it runs in any clone):

* the anonymous shelf renders the public set ONLY: rated fixtures with
  their stars painted exactly as the owner sees them, the wishlist section
  — and every unrated fixture absent BY NAME, its private-only author
  absent, the year section only a private book populated rendered as if
  absent, no private id linked at all (the absence proofs are the
  deliverable, not the happy-path 200s);
* /bok + /cover answer 200 anonymous for public-set ids; for a private id
  the answer is the guard's login refuse and it is the SAME status and
  Location a nonexistent id gets — id-enumeration cannot tell them apart
  (the equal-answer legs assert both halves);
* /sok and /rekommendationer answer the guard's 302 to the login page
  anonymous and 200 to the owner (back behind the password);
* every write route refuses an anonymous POST non-2xx (unchanged from
  MC 12497), including POSTs aimed at READ paths: the method rule in
  _is_public_read is what makes "public to read" not mean "public to
  write";
* no anonymous read ever sets a session cookie, and no public page paints
  an owner door (edit page, add page, byt lösenord, logga ut, the betyg
  widget, "Visa inte igen");
* the SETUP-STATE exception: while no password is set the choose-password
  gate still wraps the whole site — every data route (public or owner)
  redirects to /satt-loesenord, and the root lands the setup door;
* the authenticated owner still sees EVERYTHING unfiltered everywhere: the
  full shelf including the private half, search, recs, and the write
  paths — her own view changed NOTHING when the public scope narrowed.

The quarantine legs (state files 404 in every state) stay in test_guard;
the corpus-scale leak + absence matrix under this same contract is
test_no_leak.
"""
import sqlite3

import pytest

from app import create_app
from tests.test_browse import PASSWORD, seed_shelf

# One extra private fixture beside seed_shelf's five: an unrated READ book
# in a year NO public book populated — the leg "sections/years with zero
# public books render as if absent" needs a private-ONLY year to mean
# anything, and the shared synthetic shelf stays untouched for its owners.
PRIVATE_ROW = (6, "Hemlig Höst", 2019, 2023, "2023-05-04", None, "bok",
               "read", None, None, None, None)
PRIVATE_AUTHOR = "Anna Anonym"

# Titles/authors the anonymous reader may never meet (fixture 3 and the
# row above: unrated read rows — the private half of the synthetic shelf).
PRIVATE_TITLES = ("Vår i Fågelkärr", "Hemlig Höst")
PRIVATE_AUTHORS = ("Ann-Charlotte Persson", PRIVATE_AUTHOR)

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


def _seed_private_only_year(db_path):
    conn = sqlite3.connect(db_path)
    now = "2026-11-14T00:00:00Z"
    conn.execute(
        "INSERT INTO book (id, title, year, read_year, date_read, rating,"
        " format, status, book_key, created, updated) VALUES (?,?,?,?,?,?,"
        " ?,?,?,?,?)",
        (*PRIVATE_ROW[:8], f"key-{PRIVATE_ROW[0]}", now, now))
    conn.execute("INSERT INTO author (name) VALUES (?)", (PRIVATE_AUTHOR,))
    conn.execute("INSERT INTO book_author (book_id, author_id) VALUES (?, "
                 "(SELECT id FROM author WHERE name = ?))",
                 (PRIVATE_ROW[0], PRIVATE_AUTHOR))
    conn.commit()
    conn.close()


@pytest.fixture()
def configured(tmp_path, monkeypatch):
    """The synthetic shelf + the private-only row + the password set — the
    CONFIGURED state the public-scope contract is a property of."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    _seed_private_only_year(tmp_path / "liselott.db")
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


# ── configured state: the anonymous shelf IS the public set, full stop ──────
def test_anonymous_shelf_shows_the_public_set_with_stars(configured):
    _, _ = configured
    anon = _app().test_client()
    r = anon.get("/liselott/bibliotek")
    assert r.status_code == 200
    for title in ("God jul Agnes", "Stöld", "Ta min hand"):   # rated only
        assert title in r.text
    assert 'aria-label="Betyg 4 av 5"' in r.text   # stars READ public, as seen
    assert "Att läsa" in r.text and "En bur av guld" in r.text  # wishlist too


def test_anonymous_shelf_hides_every_unrated_title_by_name(configured):
    """The absence proof, the deliverable of the narrowing: not one title,
    not one private-only author, not a count, not the year section only the
    private row populated, not one id link."""
    _, _ = configured
    anon = _app().test_client()
    body = anon.get("/liselott/bibliotek").text
    for title in PRIVATE_TITLES:
        assert title not in body, title
    for author in PRIVATE_AUTHORS:
        assert author not in body, author
    assert ">2023<" not in body          # the private-only year renders absent
    for pid in (3, 6):                   # no link into the private half at all
        assert f'href="/liselott/bok/{pid}"' not in body, pid
        assert f'"/liselott/cover/{pid}"' not in body, pid


# ── configured state: /bok + /cover — public ids answer, others refuse ─────
def test_public_ids_answer_anonymous_with_their_data(configured):
    _, _ = configured
    anon = _app().test_client()
    r = anon.get("/liselott/bok/2")
    assert r.status_code == 200
    assert "Stöld" in r.text and "Ann-Helén Laestadius" in r.text
    r = anon.get("/liselott/bok/1")             # the note ships with the page
    assert r.status_code == 200
    assert "Sommarstugeklassikern" in r.text
    r = anon.get("/liselott/bok/5")             # the wishlist row is public too
    assert r.status_code == 200 and "En bur av guld" in r.text
    r = anon.get("/liselott/cover/2")           # the stored cover, real bytes
    assert r.status_code == 200 and r.mimetype == "image/jpeg"
    r = anon.get("/liselott/cover/1")   # public book, no cover: the honest SVG
    assert r.status_code == 200 and r.mimetype == "image/svg+xml"


def test_private_id_answers_exactly_what_a_nonexistent_id_answers(configured):
    """The equal-answer legs — twice a byte, once a shape: the guard's
    login refuse for a private id and for a nonexistent id is THE SAME
    status and THE SAME Location, so id-enumeration learns nothing.
    Neither answer serves cover bytes (not even the placeholder — that is
    public-book behaviour)."""
    _, _ = configured
    anon = _app().test_client()
    for route, priv, gone in (("/liselott/bok/", 3, 9999),
                              ("/liselott/bok/", 6, 9999),
                              ("/liselott/cover/", 3, 9999),
                              ("/liselott/cover/", 6, 9999)):
        a, b = anon.get(route + str(priv)), anon.get(route + str(gone))
        assert (a.status_code, b.status_code) == (302, 302), route
        assert a.headers["Location"] == b.headers["Location"] == \
            "/liselott/logga-in", (route, priv)
        assert "Vår i Fågelkärr" not in a.text   # the refuse carries no data
    r = anon.get("/liselott/cover/3")
    assert r.mimetype != "image/svg+xml"   # a private id never gets the SVG


# ── configured state: search + recs are BACK behind the password ────────────
def test_search_and_recs_refuse_anonymous_and_answer_the_owner(configured):
    _, client = configured
    anon = _app().test_client()
    for path in ("/liselott/sok?q=Sto%3Fd", "/liselott/rekommendationer"):
        r = anon.get(path)
        assert r.status_code == 302, path
        assert r.headers["Location"] == "/liselott/logga-in", path
        assert "Stöld" not in r.text, path     # a redirect carries no data
    assert client.get("/liselott/sok?q=x").status_code == 200
    assert client.get("/liselott/rekommendationer").status_code == 200


# ── configured state: writes stay refused, cookies and doors stay away ──────
def test_write_routes_refuse_anonymous(configured):
    _, _ = configured
    anon = _app().test_client()
    for path, refuse in WRITE_ROUTES:
        r = anon.post(path, data={"x": "1"})
        assert r.status_code == refuse, (path, r.status_code)
        if refuse == 302:                       # the guard's uniform refuse
            assert r.headers["Location"] == "/liselott/logga-in", path
        assert not (200 <= r.status_code < 300), path   # never a 2xx write


def test_anonymous_reads_set_no_session_cookie(configured):
    _, _ = configured
    anon = _app().test_client()
    for path in ("/liselott/", "/liselott/bibliotek", "/liselott/bok/1",
                 "/liselott/bok/3",            # the refuse sets nothing either
                 "/liselott/cover/3", "/liselott/sok?q=Stöld",
                 "/liselott/rekommendationer"):
        r = anon.get(path)
        assert "Set-Cookie" not in r.headers, path


def test_public_pages_paint_no_owner_door(configured):
    _, _ = configured
    anon = _app().test_client()
    for path in ("/liselott/", "/liselott/bibliotek", "/liselott/bok/1",
                 "/liselott/bok/2", "/liselott/bok/5"):
        html = anon.get(path).text
        for door in ("/redigera/", "/byter-losenord", "/lagg-till",
                     "/logga-ut", "/ta-bort/", "/onska/lagg-till",
                     "Spara betyg", "Visa inte igen", "Omslag saknas"):
            assert door not in html, (path, door)


def test_public_book_page_still_shows_the_readonly_stars(configured):
    """The narrowing must not overshoot: hiding the WRITE widget may not
    hide the READ fact — book 2 carries rating 4 and the anon page paints
    it exactly as the owner sees it."""
    _, _ = configured
    anon = _app().test_client()
    assert 'aria-label="Betyg 4 av 5"' in anon.get("/liselott/bok/2").text


# ── the setup-state exception: no password -> nothing is public ─────────────
def test_fresh_state_wraps_the_whole_site(fresh):
    _, client = fresh
    anon = _app().test_client()
    assert client.get("/liselott/satt-loesenord").status_code == 200  # open
    for path in ("/bibliotek", "/bok/1", "/bok/2", "/bok/3", "/sok?q=x",
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
    r = anon.get("/liselott/robots.txt")         # crawlers told away too:
    assert r.status_code == 200                  # the site is wrapped here
    assert "Disallow: /" in r.text


def test_robots_allows_the_public_configured_site(configured):
    """robots.txt follows the state truthfully: the CONFIGURED site
    publishes its public set, so ALLOW once the password stands; the
    closed-window 404 posture is test_guard's."""
    _, _ = configured
    anon = _app().test_client()
    r = anon.get("/liselott/robots.txt")
    assert r.status_code == 200
    assert "Allow: /" in r.text and "Disallow" not in r.text


# ── the owner: everything unfiltered, everywhere — the unchanged view ───────
def test_owner_sees_the_full_shelf_including_the_private_half(configured):
    _, client = configured
    body = client.get("/liselott/bibliotek").text
    for title in ("God jul Agnes", "Stöld", "Ta min hand",
                  "En bur av guld") + PRIVATE_TITLES:
        assert title in body, title
    assert ">2023<" in body          # her private-only year section stands
    assert client.get("/liselott/bok/3").status_code == 200
    assert client.get("/liselott/bok/6").status_code == 200


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
    # grading makes the book PUBLIC (the owner ruling's mechanism, not a
    # second one): the anon page now shows it with the new rating.
    anon = _app().test_client()
    assert 'aria-label="Betyg 5 av 5"' in anon.get("/liselott/bok/3").text
    # and the owner's edit doors paint on HER pages (not on anon's)
    assert "Omslag saknas — fixa" in client.get("/liselott/bok/1").text
