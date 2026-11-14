"""MC 12522 — the public ENTRANCE at `/` (owner report 2026-11-14, verbatim):
"I want you to do a browser test of the live website sibbamala.com/liselott
. I only get to thr logga in page."

Measured cause: the anonymous landing rendered intro copy and a "Logga in"
link only — the public shelf that `/bibliotek` serves had no path from the
landing, so the public promise (MC 12501: "Rated books and their ratings as
well as whishlist shall be public. The rest behind password") was unreachable
from the door the owner actually opens. The cure is reuse, not a new
mechanism: `rot()` hands the landing `_hyllgrupper()` — the SAME read
`/bibliotek` serves (books.load_books(public_only=True) under
books.PUBLIC_SET_SQL) — and start.html includes `_hyllan.html`, the SAME
markup `/bibliotek` includes. Zero new query path, zero copied card markup,
ZERO touched auth code (the guard's root leg is MC 12451's, unchanged).

The legs, on the synthetic shelf (tests/test_browse) plus TWO private rows
seeded HERE (unrated, read-status, wishlist-less — never real titles from
data/): the anonymous landing renders the shelf cards under the intro copy and
the "Att läsa" section; it carries ZERO private rows by name, by author, by
year heading and by id link; its card links are exactly the ones `/bibliotek`
emits; the "Logga in" door stays, as the landing's footer line; the logged-in
landing is byte-for-byte the owner's shelf, her private half included; and the
WRAPPED setup state still answers its data-free landing — the entrance belongs
to the configured site only (the setup-state exception).

The corpus-scale absence proof for this page lives in tests/test_no_leak,
beside the same instrument for the shelf.
"""
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app import create_app
from tests.test_browse import PASSWORD, seed_shelf

ROOT = Path(__file__).resolve().parent.parent

# The two private fixtures THIS file owns: unrated, status='read', no
# date_read-driven wishlist — "the rest behind password". Synthetic names
# chosen to collide with nothing on the public shelf (VERIFIED: no public
# fixture title or author carries either string as a substring).
PRIVATE_ROWS = [
    (7, "Privat Pärla", 2011, 2013, "2013-04-02", None, "bok", "read",
     "Sven Synthes"),
    (8, "Gömd Trädgård", 2015, 2013, "2013-09-11", None, "bok", "read",
     "Sanna Syntetisk"),
]
PRIVATE_TITLES = tuple(row[1] for row in PRIVATE_ROWS)
PRIVATE_AUTHORS = tuple(row[8] for row in PRIVATE_ROWS)
PRIVATE_IDS = tuple(row[0] for row in PRIVATE_ROWS)
PRIVATE_ONLY_YEAR = 2013          # no public fixture was read this year

PUBLIC_TITLES = ("Goda natten Agda", "Nattfjärden", "Floden minns")   # rated fixtures
WISHLIST_TITLE = "En skatt av silver"                          # the wishlist row


def _seed_private(db_path):
    """The private half, through the real schema, in THIS test's own temp DB."""
    conn = sqlite3.connect(db_path)
    now = "2026-11-14T00:00:00Z"
    for (bid, title, year, read_year, date_read, rating, fmt, status,
         author) in PRIVATE_ROWS:
        conn.execute(
            "INSERT INTO book (id, title, year, read_year, date_read, rating,"
            " format, status, book_key, created, updated)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (bid, title, year, read_year, date_read, rating, fmt, status,
             f"key-{bid}", now, now))
        conn.execute("INSERT INTO author (name) VALUES (?)", (author,))
        conn.execute("INSERT INTO book_author (book_id, author_id) VALUES (?, "
                     "(SELECT id FROM author WHERE name = ?))", (bid, author))
    conn.commit()
    conn.close()


def _app():
    app = create_app()
    app.testing = True
    return app


@pytest.fixture()
def konfigurerad(tmp_path, monkeypatch):
    """The synthetic shelf + the private rows + the password set — the
    CONFIGURED state the public entrance is a property of."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    _seed_private(tmp_path / "liselott.db")
    owner = _app().test_client()
    assert owner.post("/liselott/satt-loesenord",
                      data={"loesenord": PASSWORD,
                            "bekrafta": PASSWORD}).status_code == 302
    return owner


@pytest.fixture()
def inslagning(tmp_path, monkeypatch):
    """No password yet, window open: the state with NO public anything."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    _seed_private(tmp_path / "liselott.db")
    return _app().test_client()


# ── 1. the entrance: the landing IS the public shelf under the intro ────────
def test_anonymous_landing_renders_the_public_shelf(konfigurerad):
    _ = konfigurerad
    body = _app().test_client().get("/liselott/").text
    assert "Liselotts bokhylla" in body                 # the intro copy stands
    assert 'class="bok-lank"' in body                   # the real cards, §9 markup
    for title in PUBLIC_TITLES + (WISHLIST_TITLE,):     # the public set, by name
        assert title in body, title
    assert 'aria-label="Betyg 4 av 5"' in body          # stars ride the card
    assert "Att läsa" in body                           # the wishlist section


def test_anonymous_landing_links_what_the_shelf_links(konfigurerad):
    """Leg 4: the landing's card links are the bok pages, and they are
    EXACTLY the set /bibliotek emits — one entrance, one shelf, so a card can
    never appear on one page and not the other."""
    _ = konfigurerad
    anon = _app().test_client()
    hrefs = lambda html: set(re.findall(r'href="(/liselott/bok/\d+)"', html))
    landing = hrefs(anon.get("/liselott/").text)
    shelf = hrefs(anon.get("/liselott/bibliotek").text)
    assert landing == shelf
    assert {f"/liselott/bok/{i}" for i in (1, 2, 4, 5)} == landing


# ── 2. the absence proof: not one private row reaches the landing ───────────
def test_anonymous_landing_carries_zero_private_rows(konfigurerad):
    _ = konfigurerad
    body = _app().test_client().get("/liselott/").text
    assert PUBLIC_TITLES[0] in body          # non-vacuity: the page is painted
    for title in PRIVATE_TITLES:
        assert title not in body, title
    for author in PRIVATE_AUTHORS:
        assert author not in body, author
    assert f">{PRIVATE_ONLY_YEAR}<" not in body      # the private-only section
    for pid in PRIVATE_IDS:                           # no link, no cover either
        assert f'href="/liselott/bok/{pid}"' not in body, pid
        assert f'"/liselott/cover/{pid}"' not in body, pid


# ── the door stays — as the landing's footer, not as the whole page ─────────
def test_anonymous_landing_keeps_the_login_door(konfigurerad):
    _ = konfigurerad
    body = _app().test_client().get("/liselott/").text
    assert 'href="/liselott/logga-in">Logga in</a>' in body
    assert 'class="landnings-dorr"' in body   # ONE line, below the shelf
    assert "Välj ditt lösenord" not in body   # the setup door is another state


# ── 3. the owner's landing: her full shelf, exactly as before ───────────────
def test_logged_in_landing_is_still_her_own_shelf(konfigurerad):
    owner = konfigurerad
    r = owner.get("/liselott/")
    assert r.status_code == 200
    assert "<h1>Din hylla</h1>" in r.text               # the owner's page, her h1
    assert 'href="/liselott/logga-ut"' in r.text        # the owner nav, not a door
    for title in PUBLIC_TITLES + (WISHLIST_TITLE,) + PRIVATE_TITLES:
        assert title in r.text, title                  # EVERYTHING, unfiltered
    assert f">{PRIVATE_ONLY_YEAR}<" in r.text
    assert "Liselotts bokhylla</h1>" not in r.text      # the public intro is gone
    assert 'class="landnings-dorr"' not in r.text       # and so is its footer door
    # And the byte proof: her landing IS the shelf page — same view, same
    # markup, so the two bodies are equal byte for byte. MC 12522 extracted the
    # sections into _hyllan.html; if that include ever drifts (a stray newline
    # is enough to change a served page), THIS leg says so.
    assert r.text == owner.get("/liselott/bibliotek").text


# ── the setup-state exception: a wrapped site has no entrance ───────────────
def test_wrapped_setup_landing_shows_no_shelf(inslagning):
    r = inslagning.get("/liselott/")
    assert r.status_code == 200                  # §6.4: the landing, never a 302
    assert 'href="/liselott/satt-loesenord">Välj ditt lösenord</a>' in r.text
    assert 'class="bok-lank"' not in r.text      # NOTHING public while wrapped
    for title in PUBLIC_TITLES + PRIVATE_TITLES:
        assert title not in r.text, title


# ── the empty public shelf: an empty page still resolves its partials ───────
def test_configured_but_empty_landing_renders(tmp_path, monkeypatch):
    """The state behind the live 500 family M8-hotfix-4 caught (a `{% from %}`
    import executes on an EMPTY page too): a configured site whose public set
    is empty must still answer the landing 200 — intro, no sections, the door —
    and never a traceback out of the shelf include. The shelf page beside it
    keeps its honest empty copy."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")          # schema, then emptied below
    conn = sqlite3.connect(tmp_path / "liselott.db")
    conn.execute("UPDATE book SET rating = NULL WHERE rating IS NOT NULL")
    conn.execute("UPDATE book SET status = 'read' WHERE status <> 'read'")
    conn.commit()
    conn.close()                                  # zero public rows, all private
    app = _app()
    assert app.test_client().post(
        "/liselott/satt-loesenord",
        data={"loesenord": PASSWORD, "bekrafta": PASSWORD}).status_code == 302
    r = app.test_client().get("/liselott/")
    assert r.status_code == 200
    assert "Liselotts bokhylla" in r.text and "logga-in" in r.text
    assert 'class="bok-lank"' not in r.text
    assert 'class="grupp"' not in r.text           # no heading over nothing
    assert "Hyllan är tom" not in r.text           # that copy is the owner's page
    assert app.test_client().get("/liselott/bibliotek").status_code == 200


# ── corpus scale: the SAME absence proof over EITHER corpus (MC 12523) ──────
PRIVATE_FLOOR = {"personal": 100, "synthetic": 20}
SEED_RC = {"personal": 0, "synthetic": 1}


def test_anonymous_landing_carries_zero_private_corpus_rows(corpus_case,
                                                            corpus_file,
                                                            tmp_path,
                                                            monkeypatch):
    """A whole seeded shelf — 700-odd rows on the personal export, 40-odd on
    the committed synthetic one, most private: EVERY unrated read row is gone
    from the landing BY NAME and its id is linked NOWHERE, while the public
    rows are present (the non-vacuity leg reads its title straight off the
    DB). Case split per MC 12523: the synthetic case runs this sweep in every
    clean clone; the personal case keeps the corpus-scale floor where the
    export resolves."""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "data-import/import_seed.py"),
         "--db", str(tmp_path / "liselott.db"), "--raw", str(corpus_file)],
        capture_output=True, text=True, cwd=str(ROOT))
    assert proc.returncode == SEED_RC[corpus_case], proc.stderr  # synthetic drifts by design
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    app = _app()
    assert app.test_client().post(
        "/liselott/satt-loesenord",
        data={"loesenord": PASSWORD, "bekrafta": PASSWORD}).status_code == 302
    conn = sqlite3.connect(tmp_path / "liselott.db")
    private = conn.execute("SELECT id, title FROM book WHERE rating IS NULL"
                           " AND status = 'read' ORDER BY id").fetchall()
    rated_title = conn.execute("SELECT title FROM book WHERE rating IS NOT"
                               " NULL ORDER BY id LIMIT 1").fetchone()[0]
    conn.close()
    assert len(private) >= PRIVATE_FLOOR[corpus_case], len(private)  # anti-vacuity
    body = app.test_client().get("/liselott/").text
    assert rated_title in body                   # the public half really painted
    for pid, title in private:
        assert title not in body, (pid, title)
        assert f'href="/liselott/bok/{pid}"' not in body, pid
