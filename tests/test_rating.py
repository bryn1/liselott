"""T5.1 — grading (plan §1: integers 1–5, NO half-steps; five radio stars with
Swedish labels; Swedish copy).

The legs the plan pins verbatim: POST 4 → shown; 6 → 400; "clear" → NULL;
unauth POST → 302. Added from §5.11 (binding status semantics): grading SETS
'read' — the one allowed wishlist→read side effect besides /onska/<id>/las —
and it never touches date_read (a grade is not a reading date). The Rensa
button posts betyg="clear" through the SAME field the radios use; when a radio
is checked AND she presses Rensa, the browser sends both values and "clear"
wins — the intent of that click is unambiguous, and this rule is pinned here
because werkzeug's .get() would otherwise return the first-sent radio.
"""
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
    app = create_app()
    app.testing = True
    client = app.test_client()
    assert client.post("/liselott/satt-loesenord",
                       data={"loesenord": PASSWORD, "bekrafta": PASSWORD}).status_code == 302
    return tmp_path, client


def token(client):
    with client.session_transaction("/liselott/logga-in") as sess:
        return sess["csrf"]


def rating_of(tmp_path, book_id):
    conn = sqlite3.connect(tmp_path / "liselott.db")
    try:
        return conn.execute("SELECT rating FROM book WHERE id = ?",
                            (book_id,)).fetchone()[0]
    finally:
        conn.close()


# ── the plan's four legs ─────────────────────────────────────────────────────
def test_post_4_is_shown_on_the_book_page(shelf):
    tmp, client = shelf
    r = client.post("/liselott/betyg/1", data={"betyg": "4", "csrf": token(client)})
    assert r.status_code == 302
    assert r.headers["Location"] == "/liselott/bok/1"
    assert rating_of(tmp, 1) == 4
    page = client.get("/liselott/bok/1")
    assert 'aria-label="Betyg 4 av 5"' in page.text     # shown, §9 star macro


def test_post_6_is_400_and_stores_nothing(shelf):
    tmp, client = shelf   # book 3 is the unrated corpus row: "nothing stored" means NULL
    r = client.post("/liselott/betyg/3", data={"betyg": "6", "csrf": token(client)})
    assert r.status_code == 400
    assert "fel-meddelande" in r.text
    assert rating_of(tmp, 3) is None


def test_post_clear_sets_rating_null(shelf):
    tmp, client = shelf
    client.post("/liselott/betyg/1", data={"betyg": "4", "csrf": token(client)})
    r = client.post("/liselott/betyg/1", data={"betyg": ["4", "clear"],
                                               "csrf": token(client)})
    assert r.status_code == 302                    # Rensa clicked with a radio
    assert rating_of(tmp, 1) is None               # checked: the clear wins


def test_unauthenticated_post_is_redirected_to_login(shelf):
    _, client = shelf
    fresh = client.application.test_client()       # no session at all
    r = fresh.post("/liselott/betyg/1", data={"betyg": "3"})
    assert r.status_code == 302
    assert r.headers["Location"] == "/liselott/logga-in"


# ── validation negatives + §5.11 status rule ─────────────────────────────────
def test_non_numeric_grade_is_400(shelf):
    tmp, client = shelf
    r = client.post("/liselott/betyg/3", data={"betyg": "bra", "csrf": token(client)})
    assert r.status_code == 400
    assert "fel-meddelande" in r.text
    assert rating_of(tmp, 3) is None


def test_zero_is_not_a_grade(shelf):
    """0 is NOT "clear" — the scale is 1–5; only the named Rensa value clears."""
    tmp, client = shelf
    r = client.post("/liselott/betyg/3", data={"betyg": "0", "csrf": token(client)})
    assert r.status_code == 400
    assert rating_of(tmp, 3) is None


def test_grading_a_wishlist_book_flips_it_to_read_without_a_date(shelf):
    """§5.11: grading ADDS status='read' (wishlist→read), and the read_year 0
    sentinel becomes the current year so the shelf groups it honestly;
    date_read is not invented (books.sw_date names the gap)."""
    tmp, client = shelf
    r = client.post("/liselott/betyg/5", data={"betyg": "5", "csrf": token(client)})
    assert r.status_code == 302
    conn = sqlite3.connect(tmp / "liselott.db")
    status, date_read, year = conn.execute(
        "SELECT status, date_read, read_year FROM book WHERE id = 5").fetchone()
    conn.close()
    assert status == "read"
    assert date_read is None
    import datetime
    assert year == datetime.date.today().year


def test_grading_never_touches_an_existing_date(shelf):
    tmp, client = shelf
    client.post("/liselott/betyg/1", data={"betyg": "3", "csrf": token(client)})
    conn = sqlite3.connect(tmp / "liselott.db")
    assert conn.execute("SELECT date_read FROM book WHERE id = 1").fetchone()[0] \
        == "2026-10-29"
    conn.close()


def test_unknown_book_is_404_and_echoes_nothing(shelf):
    client = shelf[1]
    r = client.post("/liselott/betyg/9999",
                    data={"betyg": "4", "csrf": token(client)})
    assert r.status_code == 404
    assert "Stöld" not in r.text


# ── the grading UI (§1: five radio stars, Swedish labels) ────────────────────
def test_bok_page_carries_the_five_radio_grade_form(shelf):
    page = shelf[1].get("/liselott/bok/1")
    assert 'action="/liselott/betyg/1"' in page.text
    for value in ("1", "2", "3", "4", "5"):
        assert f'value="{value}"' in page.text
    assert "Betyg 5" in page.text                    # Swedish labels, not glyphs
    assert 'value="clear"' in page.text              # Rensa posts the clear token
    assert 'name="csrf"' in page.text
