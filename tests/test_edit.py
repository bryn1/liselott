"""T5.2 — the fix-me landing page (edit) + delete.

The plan's legs: POST changes title/year/format/date_read/notes; the ISBN
field normalizes 10/13 or answers 400 in Swedish; /ta-bort/<id> (confirm)
removes the row and the bok page then 404s; editing a title/author RECOMPUTES
book_key (§5.3) — asserted, because the P1-3 upsert contract dies the moment
a stored row and its key disagree. The alias chain rides through here too: an
author typed in its misspelled form keys the row under the CANONICAL name,
the same rule the seed import obeys (T1.4).

Fields update per-field (present in the form = intended): the rapport page's
per-row ISBN input (T5.5) posts ONLY isbn13 to this same route, and must not
wipe the title by absence. Validation negatives per the brief: bad year, bad
date, bad format, bad ISBN, empty title, a key collision (the row that
already owns that title+author pair), delete without the confirm field.
"""
import sqlite3
from pathlib import Path  # noqa: F401  (state paths in the delete legs)

import pytest

from app import create_app, search, seed
from tests.test_browse import PASSWORD, seed_shelf


@pytest.fixture()
def shelf(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    app = create_app()
    app.testing = True
    client = app.test_client()
    assert client.post("/liselott/satt-loesenord",
                       data={"loesenord": PASSWORD, "bekrafta": PASSWORD}).status_code == 302
    return tmp_path, client


def token(client):
    with client.session_transaction("/liselott/logga-in") as sess:
        return sess["csrf"]


def row(tmp_path, book_id, cols):
    conn = sqlite3.connect(tmp_path / "liselott.db")
    try:
        return conn.execute(
            f"SELECT {', '.join(cols)} FROM book WHERE id = ?",
            (book_id,)).fetchone()
    finally:
        conn.close()


def save(client, book_id, **fields):
    return client.post(f"/liselott/redigera/{book_id}",
                       data={**fields, "csrf": token(client)})


# ── the edit page ────────────────────────────────────────────────────────────
def test_edit_page_shows_the_current_record(shelf):
    page = shelf[1].get("/liselott/redigera/2")
    assert page.status_code == 200
    assert 'value="Stöld"' in page.text
    assert "Ann-Helén Laestadius" in page.text
    assert 'action="/liselott/redigera/2"' in page.text
    assert 'name="csrf"' in page.text
    # OQ-2(a): the hitta-omslag paste-url form is wired on this page (the M3
    # endpoint already answers JSON; S5 gives it its button).
    assert 'action="/liselott/omslag/2/hitta"' in page.text
    assert 'name="sida_url"' in page.text
    # and the delete lives HERE, behind an explicit confirm field
    assert 'action="/liselott/ta-bort/2"' in page.text


def test_unknown_id_is_404_and_echoes_nothing(shelf):
    r = shelf[1].get("/liselott/redigera/9999")
    assert r.status_code == 404
    assert "Stöld" not in r.text


# ── the plan's core leg: the named fields change ─────────────────────────────
def test_post_changes_title_year_format_date_and_notes(shelf):
    tmp, client = shelf
    r = save(client, 3, titel="Vår i Fågelkärr (ny titel)",
             forfattare="Ann-Charlotte Persson", utgivningsar="2025",
             format="bok", last="2025-06-01", anteckningar="Lyssnad och läst.")
    assert r.status_code == 302
    got = row(tmp, 3, ["title", "year", "format", "date_read", "notes"])
    assert got == ("Vår i Fågelkärr (ny titel)", 2025, "bok", "2025-06-01",
                   "Lyssnad och läst.")
    page = client.get("/liselott/bok/3")
    assert "Vår i Fågelkärr (ny titel)" in page.text
    assert "1 juni 2025" in page.text            # Swedish date on the bok page


# ── ISBN: the ONE §7 normalizer, else 400 in Swedish ─────────────────────────
def test_isbn10_input_is_stored_normalized_both_columns(shelf):
    tmp, client = shelf
    r = save(client, 1, titel="God jul Agnes", forfattare="Kristin Emilsson",
             isbn13="91-985596-99")
    assert r.status_code == 302
    isbn13, isbn10 = row(tmp, 1, ["isbn13", "isbn10"])
    assert isbn13 == search.isbn10_to_13("9198559699")   # one mechanism, not a re-derivation
    assert isbn10 == "9198559699"


def test_valid_isbn13_accepted(shelf):
    tmp, client = shelf
    r = save(client, 1, titel="God jul Agnes", forfattare="Kristin Emilsson",
             isbn13="9789198559699")
    assert r.status_code == 302
    assert row(tmp, 1, ["isbn13"])[0] == "9789198559699"


def test_bad_isbn_is_400_says_so_in_swedish_and_changes_nothing(shelf):
    tmp, client = shelf
    before = row(tmp, 1, ["isbn13"])
    r = save(client, 1, titel="God jul Agnes", forfattare="Kristin Emilsson",
             isbn13="978919855969X")
    assert r.status_code == 400
    assert "fel-meddelande" in r.text and "ISBN" in r.text
    assert row(tmp, 1, ["isbn13"]) == before


def test_only_isbn_posted_does_not_wipe_the_title(shelf):
    """The rapport page's per-row ISBN input posts this ONE field."""
    tmp, client = shelf
    r = client.post("/liselott/redigera/1",
                    data={"isbn13": "9789198559699", "csrf": token(client)})
    assert r.status_code == 302
    assert row(tmp, 1, ["title", "isbn13"]) == ("God jul Agnes", "9789198559699")


# ── §5.3: the match key follows the identity it keys ─────────────────────────
def test_editing_title_and_author_recomputes_book_key(shelf):
    tmp, client = shelf
    before = row(tmp, 1, ["book_key"])[0]
    r = save(client, 1, titel="God jul, Agnes!", forfattare="Kristin Emilsson")
    assert r.status_code == 302
    after = row(tmp, 1, ["book_key"])[0]
    assert after != before
    assert after == seed.book_key("God jul, Agnes!", ["Kristin Emilsson"])


def test_author_spelling_is_alias_resolved_before_keying(shelf):
    """T1.4's chain applies to the edit door too: the misspelled form keys (and
    registers) under the canonical name, or the row would collide with itself
    under two spellings."""
    tmp, client = shelf
    r = save(client, 1, titel="En enda hemlighet", forfattare="Simona Ahrnsredt")
    assert r.status_code == 302
    assert row(tmp, 1, ["book_key"])[0] == seed.book_key(
        "En enda hemlighet", ["Simona Ahrnstedt"])


def test_editing_into_an_existing_books_key_is_400(shelf):
    """UNIQUE book_key is the P1-3 contract: the honest answer is a Swedish 400,
    never a silent overwrite of the other row or a 500 from SQLite. The fixture
    rows carry SYNTHETIC literal keys, so leg 1 first gives row 2 its real
    §5.3 key (the same recompute this route runs), then row 1 edits into it."""
    tmp, client = shelf
    assert save(client, 2, titel="Stöld",
                forfattare="Ann-Helén Laestadius").status_code == 302
    key2 = row(tmp, 2, ["book_key"])[0]
    assert key2 == seed.book_key("Stöld", ["Ann-Helén Laestadius"])
    r = save(client, 1, titel="Stöld", forfattare="Ann-Helén Laestadius")
    assert r.status_code == 400
    assert "fel-meddelande" in r.text
    assert row(tmp, 2, ["book_key"])[0] == key2           # the other row untouched
    assert row(tmp, 1, ["title"])[0] == "God jul Agnes"   # and this one unharmed


# ── validation negatives (the brief's edit-validation row) ───────────────────
def test_empty_title_is_400(shelf):
    tmp, client = shelf
    r = save(client, 1, titel="  ", forfattare="Kristin Emilsson")
    assert r.status_code == 400
    assert row(tmp, 1, ["title"])[0] == "God jul Agnes"


def test_non_numeric_year_is_400(shelf):
    tmp, client = shelf
    r = save(client, 1, titel="God jul Agnes", forfattare="Kristin Emilsson",
             utgivningsar="tjugotvå")
    assert r.status_code == 400


def test_impossible_date_is_400(shelf):
    tmp, client = shelf
    r = save(client, 1, titel="God jul Agnes", forfattare="Kristin Emilsson",
             last="2026-13-01")
    assert r.status_code == 400
    assert row(tmp, 1, ["date_read"])[0] == "2026-10-29"


def test_format_outside_the_vocabulary_is_400(shelf):
    """The DB CHECK ('bok','ljudbok') would 500 — validated before the write,
    answered 400 in Swedish (a CHECK violation is not a product surface)."""
    tmp, client = shelf
    r = save(client, 1, titel="God jul Agnes", forfattare="Kristin Emilsson",
             format="cd")
    assert r.status_code == 400
    assert row(tmp, 1, ["format"])[0] == "bok"


# ── delete ───────────────────────────────────────────────────────────────────
def test_ta_bort_removes_the_row_and_its_orbits(shelf):
    tmp, client = shelf
    (tmp / "covers").mkdir()
    (tmp / "covers" / "2.jpg").write_bytes(b"jpegbytes")   # stored cover of book 2
    r = client.post("/liselott/ta-bort/2",
                    data={"bekrafta": "ta bort", "csrf": token(client)})
    assert r.status_code == 302
    conn = sqlite3.connect(tmp / "liselott.db")
    assert conn.execute("SELECT 1 FROM book WHERE id = 2").fetchone() is None
    assert conn.execute("SELECT COUNT(*) FROM book_author WHERE book_id = 2").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM book_genre WHERE book_id = 2").fetchone()[0] == 0
    conn.close()
    assert not (tmp / "covers" / "2.jpg").exists()   # no orphaned cover bytes
    assert client.get("/liselott/bok/2").status_code == 404


def test_ta_bort_without_the_confirm_field_is_400(shelf):
    tmp, client = shelf
    r = client.post("/liselott/ta-bort/2", data={"csrf": token(client)})
    assert r.status_code == 400
    conn = sqlite3.connect(tmp / "liselott.db")
    assert conn.execute("SELECT 1 FROM book WHERE id = 2").fetchone() is not None
    conn.close()


def test_unauthenticated_post_is_redirected(shelf):
    fresh = shelf[1].application.test_client()
    for path in ("/liselott/redigera/2", "/liselott/ta-bort/2"):
        r = fresh.post(path, data={})
        assert r.status_code == 302, path
        assert r.headers["Location"] == "/liselott/logga-in", path
