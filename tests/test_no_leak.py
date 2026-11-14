"""T2.6 — the leak matrix: the no-data-reachable-unauthenticated guarantee,
run over a SEEDED database. Corpus leg (path F, MC 12451 c5): the seed needs
the personal export, so the `corpus` fixture skips these with a loud reason
where it is unresolvable and seeds the pinned one where it exists. Unauthenticated
bodies carry zero seed bytes in the configured state AND in the closed-window
state over the same route list; /robots.txt is the only content served to
anonymous visitors; /sitemap.xml exists not."""
import subprocess
import sys
from pathlib import Path

import pytest

from app import create_app

ROOT = Path(__file__).resolve().parent.parent
PASSWORD = "_test_losenord_"

# Titles VERIFIED present in the audited corpus (T1.x golden rows).
SEEDED_TITLES = ("Stöld", "Ellens val", "Falska toner", "Näktergalen")

ROUTES = ("/", "/bibliotek", "/sok?q=Stöld", "/bok/1", "/cover/1",
          "/rekommendationer", "/onska", "/rapa/omslag", "/x",
          # M8-hotfix-2 (MC 12451): the guard 404s anonymous file-shaped
          # unknowns instead of 302-ing them (lane quarantine posture) — the
          # 404 body is static 404.html copy and carries zero seed bytes by
          # construction; these legs assert exactly that over the seeded DB.
          "/DESIGN.md", "/LEDGER.md", "/README.md", "/hosting.yaml",
          "/data-import/import_overrides.csv", "/server.py")


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


def test_unauthenticated_leak_matrix(seeded):
    """Configured state: the ROOT answers its public landing 200 (M8 staging
    gate, MC 12451 — and stays over the gate's 256 B floor, asserted so no
    future trim silently breaks the publish), every data route 302s (or 404s
    — a path that exists not), and NO body — landing included — carries a
    single seed title."""
    _, client = configured_client(seeded)
    for entry in ROUTES:
        r = client.get(entry)
        if entry == "/":
            assert r.status_code == 200, entry  # the landing leg, not a 302
            assert len(r.data) > 256, entry      # the staging gate's floor
        else:
            assert r.status_code in (302, 404), entry
        assert_no_seed_bytes(r)


def test_sitemap_absent_robots_present(seeded):
    """No sitemap route exists (§6.4): the LOGGED-IN leg sees the honest 404.
    Unauthenticated /sitemap.xml is the guard's own 404 too — the dot makes
    it file-shaped (M8-hotfix-2); an extension-less unknown stays the T2.6
    302. Neither shape serves bytes."""
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
    """F-5's hard leg: pw unset + aged window on a SEEDED database — zero
    seed bytes leak ANYWHERE, in every answer shape. The shape itself is
    the F-E/F-F contract (MC 12451): the quarantined file-shaped names 404
    in the closed state too (a probe reads a 200 there as "reachable"),
    while everything shapeless keeps answering the §6.1-pinned gate page.
    The leak claim — the one this file exists for — is unchanged: it holds
    over 404.html copy exactly as over the gate page."""
    import time

    import app.auth as auth
    app = create_app()
    app.testing = True
    monkeypatch.setattr(auth, "START_TIME", time.time() - auth.SETUP_WINDOW_S - 1)
    client = app.test_client()
    for entry in ROUTES:
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
