"""T4.2 — the shelf and the book page (§9 copy, F-3 url_for-only markup).

A synthetic SEEDED SUBSET (schema + SQL inserts, corpus-free per §13 — this
test runs in any clone): three read rows across three read_years, one with no
author, one ljudbok, one unrated, plus a wishlist row. The legs: /bibliotek
renders h1 "Din hylla" with the newest read_year first and "Att läsa" LAST;
every card links the bok page and paints its cover through url_for; graded
books carry stars WITH an aria-label (never a decoration alone); /bok/<id>
shows title, authors, year, the format WORD, a Swedish date and the notes; a
row without a cover carries the fix-me link to /redigera/<id> (§9 — the bok
page only, never the cover route); an unknown id is a 404 that echoes nothing.
"""
import sqlite3
from datetime import datetime, timezone

import pytest

from app import create_app
from app.db import init_db

PASSWORD = "_test_losenord_"

# (id, title, year, read_year, date_read, rating, format, status, isbn13,
#  isbn10, cover_path, notes)
BOOKS = [
    (1, "God jul Agnes", 2026, 2026, "2026-10-29", 5, "bok", "read",
     None, None, None, "Sommarstugeklassikern, igen."),
    (2, "Stöld", 2022, 2025, "2025-11-05", 4, "bok", "read",
     "9789198559699", "9198559699", "covers/2.jpg", None),
    (3, "Vår i Fågelkärr", 2024, 2024, None, None, "ljudbok", "read",
     None, None, None, None),
    (4, "Ta min hand", None, 2024, "2024-03-01", 3, "bok", "read",
     None, None, None, None),
    (5, "En bur av guld", 2024, 0, None, None, "bok", "wishlist",
     None, None, None, None),
]
AUTHORS = {1: ["Kristin Emilsson"], 2: ["Ann-Helén Laestadius"],
           3: ["Ann-Charlotte Persson"], 4: [], 5: ["Camilla Läckberg"]}
GENRES = {2: ["Kriminalitet"], 5: ["Romantik"]}


@pytest.fixture()
def shelf(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    conn = sqlite3.connect(tmp_path / "liselott.db")
    init_db(conn)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for (bid, title, year, read_year, date_read, rating, fmt, status,
         isbn13, isbn10, cover, notes) in BOOKS:
        conn.execute(
            "INSERT INTO book (id, title, year, read_year, date_read, rating,"
            " format, status, book_key, isbn13, isbn10, cover_path, notes,"
            " cover_source, created, updated) VALUES (?,?,?,?,?,?,?,?,?,?,?,"
            " ?,?,?,?,?)",
            (bid, title, year, read_year, date_read, rating, fmt, status,
             f"key-{bid}", isbn13, isbn10, cover, notes,
             "openlibrary" if cover else None, now, now))
        for name in AUTHORS[bid]:
            conn.execute("INSERT OR IGNORE INTO author (name) VALUES (?)",
                         (name,))
            author_id = conn.execute("SELECT id FROM author WHERE name = ?",
                                     (name,)).fetchone()[0]
            conn.execute("INSERT OR IGNORE INTO book_author (book_id,"
                         " author_id) VALUES (?,?)", (bid, author_id))
        for name in GENRES.get(bid, []):
            conn.execute("INSERT OR IGNORE INTO genre (name) VALUES (?)",
                         (name,))
            genre_id = conn.execute("SELECT id FROM genre WHERE name = ?",
                                    (name,)).fetchone()[0]
            conn.execute("INSERT OR IGNORE INTO book_genre (book_id, genre_id)"
                         " VALUES (?,?)", (bid, genre_id))
    conn.commit()
    conn.close()

    app = create_app()
    app.testing = True
    client = app.test_client()
    assert client.post("/liselott/satt-loesenord",
                       data={"loesenord": PASSWORD, "bekrafta": PASSWORD}).status_code == 302
    return client


# ── /bibliotek ──────────────────────────────────────────────────────────────
def test_shelf_h1_and_copy(shelf):
    r = shelf.get("/liselott/bibliotek")
    assert r.status_code == 200
    assert "<h1>Din hylla</h1>" in r.text
    assert 'lang="sv"' in r.text


def test_shelf_groups_read_year_newest_first(shelf):
    r = shelf.get("/liselott/bibliotek")
    positions = {year: r.text.index(f">{year}<") for year in (2026, 2025, 2024)}
    assert positions[2026] < positions[2025] < positions[2024]
    # every seeded read title is on the page
    for title in ("God jul Agnes", "Stöld", "Vår i Fågelkärr", "Ta min hand"):
        assert title in r.text


def test_shelf_wishlist_section_is_last(shelf):
    r = shelf.get("/liselott/bibliotek")
    assert "Att läsa" in r.text
    assert r.text.index(">2024<") < r.text.index("Att läsa")
    assert "En bur av guld" in r.text
    assert r.text.index("En bur av guld") > r.text.index("Att läsa")


def test_shelf_card_links_are_prefix_absolute(shelf):
    r = shelf.get("/liselott/bibliotek")
    for bid in (1, 2, 3, 4, 5):
        assert f'href="/liselott/bok/{bid}"' in r.text
        assert f'src="/liselott/cover/{bid}"' in r.text


def test_shelf_stars_carry_an_aria_label(shelf):
    r = shelf.get("/liselott/bibliotek")
    assert 'aria-label="Betyg 5 av 5"' in r.text
    assert 'aria-label="Betyg 4 av 5"' in r.text
    # an unrated row shows NO stars at all (a zero-star graphic would be a lie)
    assert 'aria-label="Betyg 3 av 5"' in r.text
    assert r.text.count("av 5") == 3


def test_shelf_marks_the_ljudbok_format(shelf):
    r = shelf.get("/liselott/bibliotek")
    assert "Ljudbok" in r.text


# ── /bok/<id> ───────────────────────────────────────────────────────────────
def test_bok_page_shows_the_record(shelf):
    r = shelf.get("/liselott/bok/1")
    assert r.status_code == 200
    assert "<h1>God jul Agnes</h1>" in r.text
    assert "Kristin Emilsson" in r.text
    assert "2026" in r.text
    assert "Bok" in r.text
    assert "29 oktober 2026" in r.text               # Swedish date, §9 voice
    assert "Sommarstugeklassikern, igen." in r.text   # notes
    assert 'aria-label="Betyg 5 av 5"' in r.text


def test_bok_page_ljudbok_and_missing_author_are_honest(shelf):
    # the ljudbok row: format in Swedish, and its read date is NULL in the
    # seed — the gap is named, never filled with an invented date
    ljudbok = shelf.get("/liselott/bok/3")
    assert "Ljudbok" in ljudbok.text
    assert "Utan läsdatum" in ljudbok.text
    assert "Okänt år" not in ljudbok.text        # it does have a year
    # the author-less row: say so, do not print an empty separator
    utan = shelf.get("/liselott/bok/4")
    assert "Okänd författare" in utan.text


def test_bok_page_cover_img_uses_the_cover_route(shelf):
    r = shelf.get("/liselott/bok/2")
    assert 'src="/liselott/cover/2"' in r.text
    assert 'alt="Omslag till Stöld"' in r.text


def test_bok_page_shows_the_fix_me_link_only_without_a_cover(shelf):
    r = shelf.get("/liselott/bok/1")          # cover_path IS NULL
    assert "Omslag saknas — fixa" in r.text
    assert 'href="/liselott/redigera/1"' in r.text
    covered = shelf.get("/liselott/bok/2")    # has a cover -> no fix-me row
    assert "Omslag saknas" not in covered.text


def test_unknown_id_is_404_and_echoes_nothing(shelf):
    r = shelf.get("/liselott/bok/9999")
    assert r.status_code == 404
    assert "hittas inte" in r.text
    for title in ("Stöld", "God jul Agnes", "En bur av guld"):
        assert title not in r.text          # no diary bytes on an error page


def test_anonymous_reader_never_sees_the_shelf(shelf):
    """§6.4 stays true with real pages: a fresh client (no session) is turned
    away from both pages before any book row is read."""
    app = create_app()
    app.testing = True
    anon = app.test_client()
    for path in ("/liselott/bibliotek", "/liselott/bok/1"):
        r = anon.get(path)
        assert r.status_code == 302
        assert "Stöld" not in r.text
