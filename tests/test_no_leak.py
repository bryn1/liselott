"""T2.6 — the leak matrix, re-cut for the public-read contract (MC 12497,
owner ruling 2026-11-14: "The website sibbamala.com/liselott should be
public. All rate books should be public. Rating and whishing is blocked
behind liselotts password"), run over a SEEDED database.

The claim moved, the instrument did not: the READ set MAY now carry seed
bytes — a public shelf that rendered nothing would be the bug — while every
OWNER surface, every quarantined name and every refused anonymous write
still carries ZERO seed bytes. The closed-window state keeps the whole old
T2.6 claim over the same route list (the setup-state exception: while no
password is set, nothing is public). /robots.txt is served to anonymous
visitors in both open states (the robots legs state WHICH answer belongs
to which state); /sitemap.xml exists not. Corpus leg (path F, MC 12451 c5):
the seed needs the personal export, so the `corpus` fixture skips these
with a loud reason where it is unresolvable and seeds the pinned one where
it exists.
"""
import subprocess
import sys
from pathlib import Path

import pytest

from app import create_app

ROOT = Path(__file__).resolve().parent.parent
PASSWORD = "_test_losenord_"

# Titles VERIFIED present in the audited corpus (T1.x golden rows).
SEEDED_TITLES = ("Stöld", "Ellens val", "Falska toner", "Näktergalen")

# The MC 12497 read set. "/" is deliberately NOT here for the leak claim:
# its landing is still fixed copy with zero app data (M8 staging gate).
PUBLIC_ROUTES = ("/bibliotek", "/sok?q=Stöld", "/bok/1", "/cover/1",
                 "/rekommendationer")

# Owner surfaces: behind the session on a configured site (writing is
# private) — these must stay byte-silent to an anonymous visitor.
OWNER_ROUTES = ("/onska", "/lagg-till", "/redigera/1", "/rapa/omslag",
                "/byter-losenord", "/backup", "/logga-ut", "/x")

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


def test_public_reads_answer_and_owner_surfaces_stay_silent(seeded):
    """Configured state (MC 12497): the read set answers the anonymous
    visitor with the real route (200 — and the shelf leg proves the
    instrument is not vacuous by demanding a seeded title ON the page);
    the landing keeps its fixed-copy contract: 200, >256 B, zero seed
    bytes; owner surfaces 302, quarantined names 404, all byte-silent."""
    _, client = configured_client(seeded)
    r = client.get("/")
    assert r.status_code == 200                # the landing leg, not a 302
    assert len(r.data) > 256                   # the staging gate's floor
    assert_no_seed_bytes(r)                    # the landing is still ZERO data
    for entry in PUBLIC_ROUTES:
        r = client.get(entry)
        assert r.status_code == 200, entry     # the real page, not a refuse
        assert "Location" not in r.headers, entry
    assert "Stöld" in client.get("/bibliotek").text   # non-vacuity: data reads
    assert "Stöld" in client.get("/sok?q=Stöld").text
    for entry in OWNER_ROUTES:
        r = client.get(entry)
        assert r.status_code in (302, 404), entry
        assert_no_seed_bytes(r)
    for entry in QUARANTINE_NAMES:
        r = client.get(entry)
        assert r.status_code == 404, entry
        assert_no_seed_bytes(r)


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
    302. Neither shape serves bytes. /robots.txt answers 200; the ALLOW flip
    for the public site is the robots concern (MC 12497 c3) and flips this
    leg's expectation in that commit."""
    _, client = configured_client(seeded)
    r = client.get("/liselott/sitemap.xml")
    assert r.status_code == 404  # authed: the route exists not
    assert_no_seed_bytes(r)
    r = client.get("/sitemap.xml")
    assert r.status_code in (302, 404)
    assert_no_seed_bytes(r)
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert "Disallow: /" in r.text


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
