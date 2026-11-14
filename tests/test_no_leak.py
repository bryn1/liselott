"""T2.6 — the leak matrix, re-cut for the public-SCOPE contract (MC 12501,
owner ruling 2026-11-14, verbatim: "Rated books and their ratings as well
as whishlist shall be public. The rest behind password" — narrowing MC
12497's same-day broader read claim), run over a SEEDED database.

The claim narrowed, the instrument did not: the public READ set (the shelf
filtered to the public set, public-set /bok and /cover) MAY carry seed
bytes — a public shelf that rendered nothing would be the bug — while
EVERY PRIVATE row must carry NONE of them: all 700 unrated corpus titles
and ids are grepped out of the anonymous shelf BY NAME (a corpus-scale
absence proof the synthetic shelf cannot fake), the search and rec
surfaces are back on the refused-and-silent list, and every quarantined
name and refused anonymous write still carries ZERO seed bytes. The
closed-window state keeps the whole old T2.6 claim over the same route
list (the setup-state exception: while no password is set, nothing is
public). /robots.txt is served to anonymous visitors in both open states
(the robots legs state WHICH answer belongs to which state);
/sitemap.xml exists not. Corpus leg (path F, MC 12451 c5): the seed needs
the personal export, so the `corpus` fixture skips these with a loud
reason where it is unresolvable and seeds the pinned one where it exists.
"""
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app import create_app

ROOT = Path(__file__).resolve().parent.parent
PASSWORD = "_test_losenord_"

# Titles VERIFIED present in the audited corpus (T1.x golden rows).
SEEDED_TITLES = ("Stöld", "Ellens val", "Falska toner", "Näktergalen")

# The MC 12501 read set, WITHOUT the id-dependent legs (public ids resolve
# from the seeded DB at run time — see _public_ids): the shelf is the one
# route whose public answer never depends on picking an id here. "/" is
# deliberately NOT here for the leak claim: its landing is still fixed copy
# with zero app data (M8 staging gate).
PUBLIC_ROUTES = ("/bibliotek",)

# Owner + read-private surfaces: behind the session on a configured site
# (MC 12501: search and the rec surface joined these again) — these must
# stay byte-silent to an anonymous visitor.
OWNER_ROUTES = ("/onska", "/lagg-till", "/redigera/1", "/rapa/omslag",
                "/byter-losenord", "/backup", "/logga-ut", "/x",
                "/sok?q=Stöld", "/rekommendationer")

# M8-hotfix-2 (MC 12451): mirror-DROPPED root names — the guard's own 404,
# unchanged in every state, asserted over the seeded DB so a leak of a
# quarantined name would carry corpus bytes loudly.
QUARANTINE_NAMES = ("/DESIGN.md", "/LEDGER.md", "/README.md", "/hosting.yaml",
                    "/data-import/import_overrides.csv", "/server.py")

# Every anonymous write the app knows, plus the configured setup door.
WRITE_ROUTES = ("/betyg/1", "/onska/lagg-till", "/onska/1/las", "/redigera/1",
                "/ta-bort/1", "/lagg-till", "/djem/book/1", "/omslag/1",
                "/omslag/1/hitta", "/omslag/1/ladda-up", "/byter-losenord",
                "/seed", "/bundle", "/backfill", "/satt-loesenord",
                "/bibliotek", "/bok/1")


def seed_dir(tmp_path, raw):
    """Seal the corpus into the tmp state dir through the REAL CLI (T1.6)."""
    r = subprocess.run(
        [sys.executable, str(ROOT / "data-import/import_seed.py"),
         "--db", str(tmp_path / "liselott.db"), "--raw", str(raw)],
        capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 0, f"seed CLI failed: {r.stdout}{r.stderr}"


@pytest.fixture()
def seeded(corpus, tmp_path, monkeypatch):
    seed_dir(tmp_path, corpus)
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    return tmp_path


def configured_client(seeded):
    app = create_app()
    app.testing = True
    client = app.test_client()
    r = client.post("/liselott/satt-loesenord",
                    data={"loesenord": PASSWORD, "bekrafta": PASSWORD})
    assert r.status_code == 302
    return app, client


def assert_no_seed_bytes(response):
    for title in SEEDED_TITLES:
        assert title not in response.text, (title, response.request.path)


def _rows(seeded, sql):
    conn = sqlite3.connect(seeded / "liselott.db")
    rows = conn.execute(sql).fetchall()
    conn.close()
    return rows


def test_public_reads_answer_and_owner_surfaces_stay_silent(seeded):
    """Configured state (MC 12501): the public route answers the anonymous
    visitor with the real (FILTERED) page — 200 — and public-set /bok and
    /cover ids answer 200 with their data; the non-vacuity leg demands a
    RATED seeded title on the shelf (not just any seed byte); the landing
    keeps its fixed-copy contract: 200, >256 B, zero seed bytes; owner and
    read-private surfaces 302, quarantined names 404, all byte-silent."""
    _, client = configured_client(seeded)
    r = client.get("/")
    assert r.status_code == 200                # the landing leg, not a 302
    assert len(r.data) > 256                   # the staging gate's floor
    assert_no_seed_bytes(r)                    # the landing is still ZERO data
    rated_id, rated_title, wishlist_id = _public_ids(seeded)
    for entry in PUBLIC_ROUTES + (f"/bok/{rated_id}", f"/bok/{wishlist_id}",
                                  f"/cover/{rated_id}"):
        r = client.get(entry)
        assert r.status_code == 200, entry     # the real page, not a refuse
        assert "Location" not in r.headers, entry
    assert rated_title in client.get("/bibliotek").text   # non-vacuity: a
    # rated row reads public, and every golden-row title here is UNRATED —
    # the same instrument that let MC 12497 demand "Stöld" now demands its
    # ABSENCE (see test_private_corpus_rows_are_absent_from_the_anon_shelf).
    for entry in OWNER_ROUTES:
        r = client.get(entry)
        assert r.status_code in (302, 404), entry
        assert_no_seed_bytes(r)
    for entry in QUARANTINE_NAMES:
        r = client.get(entry)
        assert r.status_code == 404, entry
        assert_no_seed_bytes(r)


def _public_ids(seeded):
    """(rated id, rated title, wishlist id) straight off the seeded DB —
    the public legs resolve their ids from the data, never from a guess."""
    rated = _rows(seeded, "SELECT id, title FROM book WHERE rating IS NOT"
                          " NULL ORDER BY id LIMIT 1")[0]
    wish = _rows(seeded, "SELECT id FROM book WHERE status <> 'read'"
                        " ORDER BY id LIMIT 1")[0][0]
    return rated[0], rated[1], wish


def test_private_corpus_rows_are_absent_from_the_anon_shelf(seeded):
    """THE absence proof at corpus scale — the deliverable of the
    narrowing: EVERY unrated corpus book (700 rows) is gone from the
    anonymous shelf by NAME — its title a raw substring check (VERIFIED
    this suite's development: zero private title is a substring of any
    public title, so no collision can excuse a hit) — and its id is linked
    NOWHERE. The private /bok and /cover ids answer the uniform login
    refuse, byte-identical in shape to a nonexistent id's answer."""
    _, client = configured_client(seeded)
    body = client.get("/bibliotek").text
    private = _rows(seeded, "SELECT id, title FROM book WHERE rating IS"
                            " NULL AND status = 'read' ORDER BY id")
    assert len(private) >= 100, len(private)   # anti-vacuity: the sweep is real
    for pid, title in private:
        assert title not in body, (pid, title)
        assert f'href="/liselott/bok/{pid}"' not in body, pid
    gone = max(pid for pid, _ in private) + 10 ** 6
    for pid, _title in private[:25]:           # a sample of the equal-answer
        r = client.get(f"/bok/{pid}")          # legs across the id space
        assert r.status_code == 302, pid
        assert_no_seed_bytes(r)
    r_gone = client.get(f"/bok/{gone}")
    assert r_gone.status_code == 302
    assert r_gone.headers["Location"] == \
        client.get(f"/bok/{private[0][0]}").headers["Location"]
    assert client.get(f"/cover/{private[0][0]}").status_code == 302
    assert client.get(f"/cover/{gone}").status_code == 302


def test_anonymous_writes_are_refused_and_silent(seeded):
    """NEVER 2xx on an anonymous write (the route contract's refuse — the
    guard's 302, or the retired setup door's 404) — and the refuse body
    carries zero seed bytes, write door or read-path-aimed POST alike."""
    _, client = configured_client(seeded)
    for entry in WRITE_ROUTES:
        r = client.post(entry, data="x")
        assert r.status_code in (302, 404), (entry, r.status_code)
        assert not (200 <= r.status_code < 300), entry
        assert_no_seed_bytes(r)


def test_sitemap_absent_robots_present(seeded):
    """No sitemap route exists (§6.4): the LOGGED-IN leg sees the honest 404.
    Unauthenticated /sitemap.xml is the guard's own 404 too — the dot makes
    it file-shaped (M8-hotfix-2); an extension-less unknown stays the T2.6
    302. Neither shape serves bytes. /robots.txt answers 200 and ALLOWS the
    configured site (MC 12501 — the site publishes its public set; the
    fresh-state Disallow leg lives in tests/test_public_read)."""
    _, client = configured_client(seeded)
    r = client.get("/liselott/sitemap.xml")
    assert r.status_code == 404  # authed: the route exists not
    assert_no_seed_bytes(r)
    r = client.get("/sitemap.xml")
    assert r.status_code in (302, 404)
    assert_no_seed_bytes(r)
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert "Allow: /" in r.text
    assert "Disallow" not in r.text


def test_closed_window_over_seeded_db(seeded, monkeypatch):
    """F-5's hard leg, unchanged by MC 12497 — it IS the setup-state
    exception at the corpus scale: pw unset + aged window on a SEEDED
    database, zero seed bytes leak ANYWHERE, in every answer shape. The
    shape itself is the F-E/F-F contract (MC 12451): the quarantined
    file-shaped names 404 in the closed state too (a probe reads a 200
    there as "reachable"), while everything shapeless — the public reads
    included, because this state has no public — keeps answering the
    §6.1-pinned gate page."""
    import time

    import app.auth as auth
    app = create_app()
    app.testing = True
    monkeypatch.setattr(auth, "START_TIME", time.time() - auth.SETUP_WINDOW_S - 1)
    client = app.test_client()
    for entry in PUBLIC_ROUTES + OWNER_ROUTES + QUARANTINE_NAMES:
        r = client.get(entry)
        assert_no_seed_bytes(r)
        if "." in entry.rsplit("/", 1)[-1]:       # file-shaped quarantine
            assert r.status_code == 404, entry
        else:
            assert "Inställningsfönstret är stängt." in r.text, entry
    assert client.get("/healthz").data == b"ok"


def test_seed_actually_ran(seeded):
    """Guard against a vacuously green matrix: the DB behind this test MUST
    contain the titles the other legs grep for."""
    import sqlite3
    conn = sqlite3.connect(seeded / "liselott.db")
    for title in SEEDED_TITLES:
        n = conn.execute("SELECT COUNT(*) FROM book WHERE title LIKE ?",
                         (f"%{title}%",)).fetchone()[0]
        assert n >= 1, title
    conn.close()
