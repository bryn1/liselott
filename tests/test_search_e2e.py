"""T4.3 — the search page over the SEEDED corpus: all five §7 keys end to end.

Case posture (MC 12523): this file seeds the COMMITTED SYNTHETIC corpus —
Swedish-shaped invented rows pinned below — so every leg RUNS in a clean
clone; the personal export is not needed (and its titles may never be named
here). The personal corpus stays pinned at scale by the corpus-case files
(seed_parse, seed_cli, seed_digest, seed_load, no_leak). Nothing here reads the
build DB. The corpus is
sealed into a tmp state dir through the REAL seed CLI (T1.6 — which for the
synthetic corpus DRIFTS off §5.9's personal audited table and exits 1 by
design; the committed db is what this file tests), then the two columns
enrichment/bundle fill in production are written on the seeded rows by this
fixture — isbn13 and the genre labels. That is stated rather than hidden: the
seed writes neither, so without the attach the ISBN and genre keys would be
tested against an empty hole instead of against her books.

Keys asserted, one GET each: ISBN (hyphenated), title, author, year, genre —
plus the no-hits state the reader actually needs to see."""
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app import create_app
from tests.test_browse import seed_shelf   # the synthetic, corpus-free shelf

ROOT = Path(__file__).resolve().parent.parent
PASSWORD = "_test_losenord_"
NATT = "Nattfjärden"
NATT_13 = "9789173710015"


def seed_dir(tmp_path, raw, expect_rc):
    r = subprocess.run(
        [sys.executable, str(ROOT / "data-import/import_seed.py"),
         "--db", str(tmp_path / "liselott.db"), "--raw", str(raw)],
        capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == expect_rc, f"seed CLI: {r.stdout}{r.stderr}"


def attach_enrichment_holes(tmp_path):
    """The two enrichment/bundle columns, written on SEEDED rows (see module
    docstring). 'Romantik' goes on a real corpus title, not on a fake book."""
    conn = sqlite3.connect(tmp_path / "liselott.db")
    row = conn.execute("SELECT id FROM book WHERE title = ?",
                       (NATT,)).fetchone()
    assert row is not None, "the synthetic corpus moved: Nattfjärden is gone"
    conn.execute("UPDATE book SET isbn13 = ?, isbn10 = ? WHERE id = ?",
                 (NATT_13, "9173710016", row[0]))
    conn.execute("INSERT INTO genre (name) VALUES ('Kriminalitet')")
    genre_id = conn.execute("SELECT id FROM genre WHERE name = 'Kriminalitet'",
                            ).fetchone()[0]
    conn.execute("INSERT INTO book_genre (book_id, genre_id) VALUES (?,?)",
                 (row[0], genre_id))
    romance = conn.execute(
        "SELECT id FROM book WHERE title = 'Den orädda cellisten'").fetchone()
    assert romance is not None, "the synthetic corpus moved: wishlist row gone"
    conn.execute("INSERT INTO genre (name) VALUES ('Romantik')")
    rom_id = conn.execute("SELECT id FROM genre WHERE name = 'Romantik'",
                          ).fetchone()[0]
    conn.execute("INSERT INTO book_genre (book_id, genre_id) VALUES (?,?)",
                 (romance[0], rom_id))
    conn.commit()
    conn.close()


@pytest.fixture()
def client(synth_seed, tmp_path, monkeypatch):
    # synthetic corpus: the CLI exits 1 on the §5.9 drift (pinned exit).
    seed_dir(tmp_path, synth_seed, 1)
    attach_enrichment_holes(tmp_path)
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    app = create_app()
    app.testing = True
    client = app.test_client()
    assert client.post("/liselott/satt-loesenord", data={
        "loesenord": PASSWORD, "bekrafta": PASSWORD}).status_code == 302
    return client


def search(client, q):
    return client.get("/liselott/sok", query_string={"q": q})


# ── the five keys ───────────────────────────────────────────────────────────
def test_key_isbn_hyphenated_hits_the_book(client):
    r = search(client, "978-91-7371-001-5")
    assert r.status_code == 200
    assert NATT in r.text
    assert 'href="/liselott/bok/' in r.text


def test_key_isbn_ten_digit_hits_the_same_book(client):
    assert NATT in search(client, "91-7371-001-6").text


def test_key_author_hits_every_book_by_her(client):
    r = search(client, "Ekelund")
    assert r.status_code == 200
    for title in ("Baggen", "Syrsjukan", "Skyddsrummet"):
        assert title in r.text, title


def test_key_author_result_count_matches_the_database(tmp_path, client):
    """The count line on the page IS the row count in the DB — the leg that
    keeps the five key tests from passing on one lucky card."""
    r = search(client, "Ekelund")
    conn = sqlite3.connect(tmp_path / "liselott.db")
    n = conn.execute(
        "SELECT COUNT(*) FROM book b JOIN book_author ba ON ba.book_id = b.id"
        " JOIN author a ON a.id = ba.author_id"
        " WHERE lower(a.name) LIKE '%ekelund%'").fetchone()[0]
    conn.close()
    assert n >= 10, n
    assert f"{n} träff" in r.text


def test_key_title_finds_the_accented_title_both_ways(client):
    assert "Ekliden i Björkvik" in search(client, "Björkvik").text
    # §7's "match raw too": the same query without the Swedish characters
    assert "Ekliden i Björkvik" in search(client, "Bjorkvik").text


def test_key_year_matches_the_reading_year(client):
    r = search(client, "2024")
    assert r.status_code == 200
    assert "träff" in r.text
    assert 'href="/liselott/bok/' in r.text


def test_key_genre_filters_by_genre(client):
    r = search(client, "romantik")
    assert r.status_code == 200
    assert "Den orädda cellisten" in r.text
    assert NATT not in r.text        # the crime novel is not romance


def test_key_genre_kriminalitet_hits_the_crime_novel(client):
    r = search(client, "Kriminalitet")
    assert NATT in r.text


# ── the states around the keys ──────────────────────────────────────────────
def test_no_hits_says_so_in_swedish(client):
    r = search(client, "zzzz")
    assert r.status_code == 200
    assert "Inga träffar" in r.text
    assert 'class="bok-kort"' not in r.text


def test_empty_query_prompts_instead_of_erroring(client):
    r = client.get("/liselott/sok")
    assert r.status_code == 200
    assert "<h1>Sök</h1>" in r.text
    assert "Titel, författare, ISBN" in r.text     # what she can search for
    assert "Inga träffar" not in r.text            # she has not asked yet


def test_results_are_cards_with_prefixed_urls(client):
    r = search(client, "Björkvik")
    assert 'class="bok-kort"' in r.text
    for card_src in ('src="/liselott/cover/', 'href="/liselott/bok/'):
        assert card_src in r.text
    # the form itself round-trips through the mount, not a root-absolute action
    assert 'action="/liselott/sok"' in r.text
    assert 'name="q"' in r.text


def test_search_is_behind_the_password_in_every_state(tmp_path, monkeypatch):
    """MC 12501 (owner ruling 2026-11-14, superseding MC 12497 the same
    day): search is NOT part of the public set — "The rest behind
    password". Configured: the guard's uniform 302 to the login page, the
    query never answered with data; fresh: the setup gate; owner: the real
    search, unchanged."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    app = create_app()
    app.testing = True
    r = app.test_client().get("/liselott/sok", query_string={"q": "Nattfjärden"})
    assert r.status_code == 302                       # fresh: the setup gate
    assert r.headers["Location"] == "/liselott/satt-loesenord"
    assert "Nattfjärden" not in r.text                      # a redirect, no data
    owner = app.test_client()
    assert owner.post("/liselott/satt-loesenord", data={
        "loesenord": PASSWORD, "bekrafta": PASSWORD}).status_code == 302
    r = app.test_client().get("/liselott/sok", query_string={"q": "Nattfjärden"})
    assert r.status_code == 302                       # configured: the wall
    assert r.headers["Location"] == "/liselott/logga-in"
    assert "Nattfjärden" not in r.text                      # refused, not answered
    r = owner.get("/liselott/sok", query_string={"q": "Nattfjärden"})
    assert r.status_code == 200                       # owner: the real search
    assert 'href="/liselott/bok/2"' in r.text         # a real hit, not an echo
