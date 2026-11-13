"""T5.4 — the wishlist: /onska, its add door, and the ONLY read flip.

§5.11 (binding): transitions are allowed ONLY via app routes, and
read→wishlist NEVER happens anywhere. /onska/lagg-till adds a NEW wish (a row
born with status='wishlist', the read_year 0 sentinel, no date); /onska/<id>/las
flips wishlist→read setting status, date_read = today and (via the shared
seed.mark_read) the year the shelf will group it under. Delete is T5.2's
/ta-bort/<id> — one delete door, not two.

The negative that pins the doctrine: grading a read row and CLEARING the grade
must leave status='read' — there is no door back, by construction, and this
test would go RED the day someone opens one."""
import sqlite3
from datetime import date

import pytest

from app import create_app, seed
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


def row(db_path, cols, book_id):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(f"SELECT {', '.join(cols)} FROM book WHERE id = ?",
                            (book_id,)).fetchone()
    finally:
        conn.close()


# ── the add door: a wish is BORN on the list ─────────────────────────────────
def test_lagg_till_creates_a_wish_not_a_read(shelf):
    tmp, client = shelf
    r = client.post("/liselott/onska/lagg-till",
                    data={"titel": "Nästa önskan", "forfattare": "Anna Såfjell",
                          "csrf": token(client)})
    assert r.status_code == 302
    conn = sqlite3.connect(tmp / "liselott.db")
    got = conn.execute("SELECT id, status, read_year, date_read, book_key"
                       " FROM book WHERE title = 'Nästa önskan'").fetchone()
    conn.close()
    assert got is not None
    wish_id, status, read_year, date_read, key = got
    assert status == "wishlist" and read_year == 0 and date_read is None
    assert key == seed.book_key("Nästa önskan", ["Anna Såfjell"])
    assert r.headers["Location"] == "/liselott/onska"


def test_the_wish_appears_on_the_list_and_in_the_shelf_att_lasa(shelf):
    tmp, client = shelf
    client.post("/liselott/onska/lagg-till",
                data={"titel": "Syndareskan", "forfattare": "Anna Såfjell",
                      "csrf": token(client)})
    page = client.get("/liselott/onska")
    assert "Syndareskan" in page.text
    shelf_page = client.get("/liselott/bibliotek")   # §9: "Att läsa" LAST there too
    assert "Syndareskan" in shelf_page.text


def test_empty_title_wish_is_400(shelf):
    client = shelf[1]
    r = client.post("/liselott/onska/lagg-till",
                    data={"titel": " ", "forfattare": "Någon",
                          "csrf": token(client)})
    assert r.status_code == 400
    assert "fel-meddelande" in r.text


def test_double_wish_is_400_not_two_rows(shelf):
    tmp, client = shelf
    data = {"titel": "Dubbel önskan", "forfattare": "Dubbel",
            "csrf": token(client)}
    assert client.post("/liselott/onska/lagg-till", data=data).status_code == 302
    assert client.post("/liselott/onska/lagg-till", data=data).status_code == 400
    conn = sqlite3.connect(tmp / "liselott.db")
    assert conn.execute("SELECT COUNT(*) FROM book WHERE title='Dubbel önskan'"
                        ).fetchone()[0] == 1
    conn.close()


# ── /las: the ONE wishlist→read flip (besides grading) ───────────────────────
def test_las_flips_to_read_with_todays_date(shelf):
    tmp, client = shelf
    # book 5 of the corpus is the wishlist row (En bur av guld)
    r = client.post("/liselott/onska/5/las", data={"csrf": token(client)})
    assert r.status_code == 302
    status, date_read, year = row(tmp / "liselott.db",
                                  ["status", "date_read", "read_year"], 5)
    assert status == "read"
    assert date_read == date.today().isoformat()
    assert year == date.today().year              # the 0 sentinel is replaced
    assert "En bur av guld" not in client.get("/liselott/onska").text
    assert "En bur av guld" in client.get("/liselott/bibliotek").text


def test_las_on_an_already_read_book_is_400_no_history_rewritten(shelf):
    tmp, client = shelf
    r = client.post("/liselott/onska/2/las", data={"csrf": token(client)})
    assert r.status_code == 400
    assert row(tmp / "liselott.db", ["date_read"], 2)[0] == "2025-11-05"


def test_las_unknown_id_is_404(shelf):
    client = shelf[1]
    r = client.post("/liselott/onska/9999/las", data={"csrf": token(client)})
    assert r.status_code == 404


# ── §5.11's never: read→wishlist is not a product surface ────────────────────
def test_no_door_back_to_wishlist_after_a_flip(shelf):
    """Grading then CLEARING a grade on a read row must leave status='read'.
    If anyone ever wires a route that flips back, this leg goes RED."""
    tmp, client = shelf
    client.post("/liselott/betyg/5", data={"betyg": "4", "csrf": token(client)})
    client.post("/liselott/betyg/5", data={"betyg": "clear", "csrf": token(client)})
    assert row(tmp / "liselott.db", ["status"], 5)[0] == "read"


# ── delete through the ONE door ──────────────────────────────────────────────
def test_delete_a_wish_via_ta_bort(shelf):
    tmp, client = shelf
    conn = sqlite3.connect(tmp / "liselott.db")
    wish_id = conn.execute("SELECT id FROM book WHERE status='wishlist'"
                           ).fetchone()[0]
    conn.close()
    r = client.post(f"/liselott/ta-bort/{wish_id}",
                    data={"bekrafta": "ta bort", "csrf": token(client)})
    assert r.status_code == 302
    assert row(tmp / "liselott.db", ["id"], wish_id) is None
    assert "En bur av guld" not in client.get("/liselott/onska").text


def test_unauthenticated_is_redirected(shelf):
    fresh = shelf[1].application.test_client()
    for path in ("/liselott/onska", "/liselott/onska/lagg-till",
                 "/liselott/onska/5/las"):
        r = fresh.post(path, data={}) if "lagg-till" in path or "las" in path \
            else fresh.get(path)
        assert r.status_code == 302, path
        assert r.headers["Location"] == "/liselott/logga-in", path
