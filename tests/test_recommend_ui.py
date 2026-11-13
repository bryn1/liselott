"""T6.2 — /rekommendationer + "Visa inte igen".

The page renders the T6.1 engine: every card carries data-kind="book|cand"
(the T8.8 production-acceptance hook), the reason copy comes straight from
the engine ("För att du gav"), and a wishlist card's cover goes through THE
cover route while a POOL card gets the static placeholder — a pool id is
not a book id and must never paint one (the fixture has both a book 1 and a
cand 1 on purpose). Dismiss posts the §8 'book:<id>' / 'cand:<id>' key and
the row is gone permanently; zero rated books answers the empty-state copy
"Betygsätt några böcker" while the wishlist still renders (§8's t=0 leg).
"""
import sqlite3

import pytest

from app import create_app
from tests.test_browse import PASSWORD
from tests.test_recommend import score_db


@pytest.fixture()
def page(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    conn = score_db(tmp_path / "liselott.db")
    # A real cover on the wishlist row 20 — its card must paint the cover
    # ROUTE, and no pool card may ever borrow a /cover/ URL.
    (tmp_path / "covers").mkdir()
    from tests.test_add import COVER_FIXTURE
    (tmp_path / "covers" / "20.jpg").write_bytes(COVER_FIXTURE.read_bytes())
    conn.execute("UPDATE book SET cover_path = 'covers/20.jpg',"
                 " cover_source = 'openlibrary' WHERE id = 20")
    conn.commit()
    conn.close()
    app = create_app()
    app.testing = True
    client = app.test_client()
    assert client.post("/liselott/satt-loesenord",
                       data={"loesenord": PASSWORD,
                             "bekrafta": PASSWORD}).status_code == 302
    return client, tmp_path


def token(client):
    """The session-bound form token (test_wishlist's pattern) — /djem is a
    browser POST, NOT one of the tokenless machine routes (§6.6). The path
    matters: the cookie lives under Path=/liselott (§6.3)."""
    with client.session_transaction("/liselott/logga-in") as sess:
        return sess["csrf"]


def test_page_renders_the_engine_with_data_kind(page):
    client, _ = page
    r = client.get("/liselott/rekommendationer")
    assert r.status_code == 200
    assert "<h1>Rekommendationer åt dig</h1>" in r.text
    assert "För att du gav" in r.text                    # the §8 reason copy
    assert r.text.count('data-kind="book"') == 3         # three wishes alive
    assert r.text.count('data-kind="cand"') == 7         # the whole pool
    assert "För att du gav ”Tid och tid igen” 4 i betyg av Tilde T" in r.text


def test_book_card_uses_the_cover_route_pool_card_never(page):
    """Book 20 has a real cover → its card hits /cover/20. A pool card paints
    the static placeholder: the cand id 1 must NEVER resolve to /cover/1
    (that is Nordanvind's slot — two tables, two id spaces)."""
    client, _ = page
    text = client.get("/liselott/rekommendationer").text
    assert "/liselott/cover/20" in text
    assert "/liselott/cover/1" not in text
    assert "omslag-saknas" in text                       # pool placeholder


def test_zero_rated_shows_the_empty_state_and_still_renders(page):
    client, tmp = page
    conn = sqlite3.connect(tmp / "liselott.db")
    conn.execute("UPDATE book SET rating = NULL")
    conn.commit()
    conn.close()
    text = client.get("/liselott/rekommendationer").text
    assert "Betygsätt några böcker" in text              # §8 empty-state copy
    assert text.count('data-kind="book"') == 3           # wishlist still shown


def test_dismiss_a_candidate_is_gone_permanently(page):
    client, tmp = page
    text = client.get("/liselott/rekommendationer").text
    assert "Tiden löper" in text                        # cand 5 is there
    r = client.post("/liselott/djem/cand/5", data={"csrf": token(client)})
    assert r.status_code == 302
    assert r.headers["Location"] == "/liselott/rekommendationer"
    after = client.get("/liselott/rekommendationer").text
    assert "Tiden löper" not in after
    assert after.count('data-kind="cand"') == 6
    conn = sqlite3.connect(tmp / "liselott.db")
    assert conn.execute("SELECT 1 FROM dismissed WHERE key = 'cand:5'"
                        ).fetchone() is not None
    conn.close()


def test_dismiss_a_wishlist_book_works_too_and_survives_repost(page):
    """'book:22' — the other key kind (P2-3: wishes are dismissible). A
    repeated POST is ignored (PRIMARY KEY), never a 500."""
    client, tmp = page
    assert "Morgonboken" in client.get("/liselott/rekommendationer").text
    assert client.post("/liselott/djem/book/22",
                 data={"csrf": token(client)}).status_code == 302
    after = client.get("/liselott/rekommendationer").text
    assert "Morgonboken" not in after
    assert after.count('data-kind="book"') == 2
    assert client.post("/liselott/djem/book/22",
                 data={"csrf": token(client)}).status_code == 302


def test_dismiss_unknown_or_foreign_kind_is_404(page):
    client, _ = page
    tk = token(client)
    assert client.post("/liselott/djem/cand/999",
                 data={"csrf": tk}).status_code == 404
    assert client.post("/liselott/djem/book/999",
                 data={"csrf": tk}).status_code == 404
    assert client.post("/liselott/djem/bok/1",
                 data={"csrf": tk}).status_code == 404


def test_dismiss_button_carries_the_csrf_gate(page):
    """The card form posts through the §6.6 gate like every browser POST: the
    rendered page carries the hidden session token."""
    client, _ = page
    text = client.get("/liselott/rekommendationer").text
    assert "Visa inte igen" in text
    assert 'name="csrf"' in text
    assert client.post("/liselott/djem/cand/3",
                       data={"csrf": "wrong"}).status_code == 400
