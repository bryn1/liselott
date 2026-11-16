"""MC 12597 (M11-N4) — the "AI rekommenderar" app side: the POST /ai-rek
machine door, the owner's accept/decline, the page section, the leak
posture. The door legs mirror tests/test_pris_door.py's checklist (the /pris
semantics are copied verbatim, so the pins are copied too); the UI legs ride
test_recommend_ui.py's fixture idiom (score_db + satt-loesenord + the
session csrf token). The legs this card's DoD pins, named:

* INGEST IDEMPOTENT — the same rec_key twice is ONE row (refresh in place).
* DECLINE IS PERMANENT — a declined row is not resurrected by a re-ingest,
  not by an accept POST, and never comes back to the page.
* ACCEPT WRITES THE WISH ONCE — through onska.skapa_onska (the isbn/year
  riding onto the book row proves it is THE shared writer, not a copy);
  a second accept writes no second wish; already-wished (the "redan"
  collision over two rec_keys of one book) is still one wish, accepted.
* CSRF + SESSION — the two buttons are browser POSTs: token missing or
  wrong 400s, an anonymous POST is the guard's uniform 302; unknown id is
  the plain 404 that echoes nothing (the /djem idiom).
* LEAK POSTURE — with ai_rek rows live, the anonymous answers (/, /bibliotek
  and the refused /rekommendationer itself) carry ZERO "AI rekommenderar"
  bytes, while the owner's positive page carries BOTH lists (classic recs
  AND the AI section) and rows rank by fit DESC; zero rows answer the
  empty-state line.
* THE DOOR CREDENTIAL — AI_REC_DOOR_TOKEN is 64-hex ENFORCED (a malformed
  armed env is the DISARMED door), unset/empty ⇒ 503 fail-closed writing
  nothing, owner session included; absent == wrong ⇒ ONE uniform 401 copy;
  GET /ai-rek keeps the guard's uniform 302; the owner's session rides the
  door without the token (the /pris posture verbatim, MC 12546).

PLANTED-RED (a gate that has never gone red is not a gate) — run against
the built tree THIS session, each red on its named leg, green again after
restore (file bytes byte-checked back):
* the door's kept_accept/kept_decline branch removed →
  test_declined_row_never_resurrected_nor_shown goes red (re-ingest
  resurrects the row);
* accept's `state != 'new'` guard removed → the SAME decline leg goes red
  (an accept POST resurrects a decline and writes a wish);
* the writer's UNIQUE-collision → "redan" handling removed →
  test_accept_of_an_already_wished_book_stays_one_wish goes red (the two
  rec_keys of one book 500); the second-accept leg stays green WITHOUT it
  because the accept guard short-circuits before the writer — each leg
  names the gate that actually carries it;
* the TOKEN_SHAPE arming check relaxed to mere non-empty →
  test_the_env_is_64_hex_enforced_malformed_is_disarmed goes red on all
  five malformed values (a well-BUT-wrongly-shaped env answers 200);
* auth's `_is_ai_rek_door()` guard term removed →
  test_absent_and_wrong_token_are_one_uniform_401 goes red (the door POST
  never reaches its 401 — the uniform 302 swallows the runner).
"""
import sqlite3

import pytest

from app import create_app
from tests.test_browse import PASSWORD
from tests.test_recommend import score_db

TOKEN = "a" * 64                 # a well-armed 64-hex env value
SEK = {"reason": "För att du gav Färjesång 5 i betyg", "source":
       "Dagens Nyster"}


def rec(titel="Kappor på en hatt", **över):
    row = {"title": titel, "author_name": "Ann Snok", "year": 2024,
           "isbn13": None, "fit": 0.9, **SEK}
    row.update(över)
    return row


def site(tmp_path, monkeypatch, token=TOKEN):
    """The configured site over score_db (rated books + wishes ⇒ the classic
    rec list renders), the door ARMED with `token` (None = env DELETED)."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    if token is None:
        monkeypatch.delenv("AI_REC_DOOR_TOKEN", raising=False)
    else:
        monkeypatch.setenv("AI_REC_DOOR_TOKEN", token)
    score_db(tmp_path / "liselott.db").close()
    app = create_app()
    app.testing = True
    owner = app.test_client()
    assert owner.post("/liselott/satt-loesenord",
                      data={"loesenord": PASSWORD,
                            "bekrafta": PASSWORD}).status_code == 302
    return app, owner


def csrf(client):
    """The session-bound form token (test_recommend_ui's pattern — the
    cookie lives under Path=/liselott, so the path matters)."""
    with client.session_transaction("/liselott/logga-in") as sess:
        return sess["csrf"]


def door(app, rows, token=TOKEN):
    """A runner-shaped POST: its own client, JSON array, no Origin (the
    curl posture the TOKENLESS reading allows)."""
    headers = {} if token is None else {"X-Ai-Rek-Token": token}
    return app.test_client().post("/liselott/ai-rek", json=rows,
                                  headers=headers)


def count(db_path, sql, *args):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, args).fetchone()[0]
    finally:
        conn.close()


# ── ingest: idempotence and the never-resurrected decision ──────────────────
def test_ingest_is_idempotent_same_key_lands_one_row(tmp_path, monkeypatch):
    app, _ = site(tmp_path, monkeypatch)
    r = door(app, [rec(isbn13="9789190000007")])
    assert r.status_code == 200
    assert r.get_json()["inserted"] == 1
    r2 = door(app, [rec(isbn13="9789190000007", reason="Uppdaterat skäl")])
    assert r2.get_json()["updated"] == 1
    assert count(tmp_path / "liselott.db",
                 "SELECT COUNT(*) FROM ai_rek WHERE isbn13 = ?",
                 "9789190000007") == 1
    conn = sqlite3.connect(tmp_path / "liselott.db")
    assert conn.execute("SELECT reason FROM ai_rek").fetchone()[0] \
        == "Uppdaterat skäl"        # state 'new' refreshes in place
    conn.close()


def test_declined_row_never_resurrected_nor_shown(tmp_path, monkeypatch):
    app, owner = site(tmp_path, monkeypatch)
    door(app, [rec(isbn13="9789190000007")])
    page = owner.get("/liselott/rekommendationer").get_data(as_text=True)
    rek_id = page.split('/ai-rek/')[1].split('/')[0]
    assert owner.post(f"/liselott/ai-rek/{rek_id}/decline",
                      data={"csrf": csrf(owner)}).status_code == 302
    r = door(app, [rec(isbn13="9789190000007", reason="Försök igen")])
    assert r.get_json()["kept_decline"] == 1      # door-side, not page-side
    conn = sqlite3.connect(tmp_path / "liselott.db")
    rad = conn.execute("SELECT state, reason, declined_at FROM ai_rek").fetchone()
    assert rad[0] == "decline" and rad[1] == SEK["reason"]
    assert rad[2] is not None                      # the ONE decline stamp
    conn.close()
    after = owner.get("/liselott/rekommendationer").get_data(as_text=True)
    assert "Kappor på en hatt" not in after        # gone from the page
    # and an accept POST cannot undo it either:
    owner.post(f"/liselott/ai-rek/{rek_id}/accept", data={"csrf": csrf(owner)})
    assert count(tmp_path / "liselott.db", "SELECT COUNT(*) FROM ai_rek"
                 " WHERE state = 'accept'") == 0
    assert count(tmp_path / "liselott.db", "SELECT COUNT(*) FROM book"
                 " WHERE status = 'wishlist' AND title = ?",
                 "Kappor på en hatt") == 0


# ── accept: THE one wish writer, ONE wish ───────────────────────────────────
def test_accept_writes_the_wish_once_and_rides_isbn_year(tmp_path, monkeypatch):
    app, owner = site(tmp_path, monkeypatch)
    door(app, [rec(isbn13="9789190000007")])
    conn = sqlite3.connect(tmp_path / "liselott.db")
    rek_id = conn.execute("SELECT id FROM ai_rek").fetchone()[0]
    conn.close()
    assert owner.post(f"/liselott/ai-rek/{rek_id}/accept",
                      data={"csrf": csrf(owner)}).status_code == 302
    # the book row carries the rec's isbn/year — proof it went through
    # onska.skapa_onska's signature, not a local copy of the INSERT.
    conn = sqlite3.connect(tmp_path / "liselott.db")
    rad = conn.execute("SELECT isbn13, year, read_year FROM book"
                       " WHERE status = 'wishlist' AND title = ?",
                       ("Kappor på en hatt",)).fetchone()
    assert rad == ("9789190000007", 2024, 0)       # BORN as a wish, §5.11
    conn.close()
    owner.post(f"/liselott/ai-rek/{rek_id}/accept", data={"csrf": csrf(owner)})
    assert count(tmp_path / "liselott.db", "SELECT COUNT(*) FROM book"
                 " WHERE status = 'wishlist' AND title = ?",
                 "Kappor på en hatt") == 1          # no second wish
    assert count(tmp_path / "liselott.db", "SELECT COUNT(*) FROM ai_rek"
                 " WHERE state = 'accept'") == 1


def test_accept_of_an_already_wished_book_stays_one_wish(tmp_path, monkeypatch):
    """Two rec_keys for ONE book (isbn-keyed + title/author-keyed) — the
    second accept hits the §5.3 UNIQUE collision and the writer's "redan"
    sentinel: accepted, still ONE wish row, no 500."""
    app, owner = site(tmp_path, monkeypatch)
    door(app, [rec(), rec(isbn13="9789190000007")])
    conn = sqlite3.connect(tmp_path / "liselott.db")
    ids = [r[0] for r in conn.execute("SELECT id FROM ai_rek ORDER BY id")]
    conn.close()
    tk = csrf(owner)
    for rid in ids:
        assert owner.post(f"/liselott/ai-rek/{rid}/accept",
                          data={"csrf": tk}).status_code == 302
    assert count(tmp_path / "liselott.db", "SELECT COUNT(*) FROM book"
                 " WHERE status = 'wishlist' AND title = ?",
                 "Kappor på en hatt") == 1
    assert count(tmp_path / "liselott.db", "SELECT COUNT(*) FROM ai_rek"
                 " WHERE state = 'accept'") == 2


# ── the guard/CSRF posture of the two buttons ───────────────────────────────
def test_accept_and_decline_require_the_csrf_token(tmp_path, monkeypatch):
    app, owner = site(tmp_path, monkeypatch)
    door(app, [rec()])
    conn = sqlite3.connect(tmp_path / "liselott.db")
    rid = conn.execute("SELECT id FROM ai_rek").fetchone()[0]
    conn.close()
    for verb in ("accept", "decline"):
        assert owner.post(f"/liselott/ai-rek/{rid}/{verb}").status_code == 400
        r = owner.post(f"/liselott/ai-rek/{rid}/{verb}",
                       data={"csrf": "fel"})
        assert r.status_code == 400
        assert "Säkerhetsmärket saknas" in r.get_data(as_text=True)
    assert count(tmp_path / "liselott.db",
                 "SELECT state FROM ai_rek") == "new"   # nothing touched


def test_anonymous_owner_posts_are_the_uniform_302(tmp_path, monkeypatch):
    app, _ = site(tmp_path, monkeypatch)
    anon = app.test_client()
    for verb in ("accept", "decline"):
        r = anon.post(f"/liselott/ai-rek/1/{verb}")
        assert r.status_code == 302
        assert r.headers["Location"] == "/liselott/logga-in"


def test_unknown_id_is_a_plain_404(tmp_path, monkeypatch):
    app, owner = site(tmp_path, monkeypatch)
    tk = csrf(owner)
    for verb in ("accept", "decline"):
        r = owner.post(f"/liselott/ai-rek/999999/{verb}", data={"csrf": tk})
        assert r.status_code == 404


# ── the page: the owner's positive leg, the anonymous zero-string sweep ─────
def test_owner_page_carries_both_lists_ranked_by_fit(tmp_path, monkeypatch):
    app, owner = site(tmp_path, monkeypatch)
    door(app, [rec("Lågt passar", fit=0.35), rec("Mitt emellan", fit=0.62),
               rec("Bäst av allt", fit=0.95)])
    text = owner.get("/liselott/rekommendationer").get_data(as_text=True)
    assert "<h2>AI rekommenderar</h2>" in text
    assert "För att du gav" in text                 # the classic list, alive
    assert text.count('data-kind="ai"') == 3
    pos = {t: text.index(t) for t in ("Bäst av allt", "Mitt emellan",
                                      "Lågt passar")}
    assert pos["Bäst av allt"] < pos["Mitt emellan"] < pos["Lågt passar"]


def test_zero_ai_rows_answer_the_empty_state_line(tmp_path, monkeypatch):
    app, owner = site(tmp_path, monkeypatch)
    text = owner.get("/liselott/rekommendationer").get_data(as_text=True)
    assert "<h2>AI rekommenderar</h2>" in text
    assert "Inga AI-rekommendationer ännu" in text


def test_ai_bytes_are_never_in_an_anonymous_answer(tmp_path, monkeypatch):
    """With ai_rek rows LIVE, every anonymous answer — the public shelf
    (200), the landing (200) and the refused rec page itself (the uniform
    302) — carries ZERO "AI rekommenderar" bytes: the section is composed
    only in the owner view, so a public page cannot leak it."""
    app, _ = site(tmp_path, monkeypatch)
    door(app, [rec(), rec("Annan titel", isbn13="9789190000008")])
    anon = app.test_client()
    for path in ("/liselott/", "/liselott/bibliotek",
                 "/liselott/rekommendationer"):
        r = anon.get(path)
        assert r.status_code in (200, 302), path
        assert "AI rekommenderar" not in r.get_data(as_text=True), path


# ── the door credential (the /pris posture verbatim + 64-hex arming) ───────
def test_disarmed_door_is_503_and_writes_nothing(tmp_path, monkeypatch):
    app, owner = site(tmp_path, monkeypatch, token=None)
    r = door(app, [rec()], token=None)
    assert r.status_code == 503
    # fail-closed is fail-closed: the owner's session does NOT ride a
    # disarmed door either (pris.py's posture, copied).
    assert owner.post("/liselott/ai-rek", json=[rec()]).status_code == 503
    assert count(tmp_path / "liselott.db", "SELECT COUNT(*) FROM ai_rek") == 0


@pytest.mark.parametrize("bad", ["abc", "", "a" * 63, "a" * 65, "g" * 64,
                                "A" * 64])
def test_the_env_is_64_hex_enforced_malformed_is_disarmed(tmp_path,
                                                          monkeypatch, bad):
    """A malformed armed env is the DISARMED door (503), never a weaker
    one — a 64-hex-or-nothing value means rotation mistakes fail closed."""
    app, _ = site(tmp_path, monkeypatch, token=bad)
    assert door(app, [rec()], token=bad or None).status_code == 503
    assert count(tmp_path / "liselott.db", "SELECT COUNT(*) FROM ai_rek") == 0


def test_absent_and_wrong_token_are_one_uniform_401(tmp_path, monkeypatch):
    app, _ = site(tmp_path, monkeypatch)
    body = door(app, [rec()], token=None).get_data(as_text=True)   # absent
    wrong = door(app, [rec()], token="b" * 64)
    prefix = door(app, [rec()], token=TOKEN[:63])           # byte-exact rule
    assert wrong.status_code == prefix.status_code == 401
    assert wrong.get_data(as_text=True) == body            # no oracle
    assert count(tmp_path / "liselott.db", "SELECT COUNT(*) FROM ai_rek") == 0


def test_get_on_the_door_keeps_the_uniform_302(tmp_path, monkeypatch):
    """The guard allow is the POST method ONLY (mirror of the /pris :345
    leg): a GET on /ai-rek is refused the same uniform login redirect."""
    app, _ = site(tmp_path, monkeypatch)
    r = app.test_client().get("/liselott/ai-rek")
    assert r.status_code == 302
    assert r.headers["Location"] == "/liselott/logga-in"


def test_owner_session_rides_the_door_without_the_token(tmp_path, monkeypatch):
    """MC 12546's posture, copied verbatim: her own tools post through the
    session she already holds — armed env, no header ⇒ 200."""
    app, owner = site(tmp_path, monkeypatch)
    r = owner.post("/liselott/ai-rek", json=[rec()])
    assert r.status_code == 200
    assert r.get_json()["inserted"] == 1
