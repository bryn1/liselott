"""MC 12606 (M11-N4b) — the price/sale feature is RETIRED; this file pins
what the tree proves afterwards. Owner rulings 2026-11-16, verbatim: "Books
on sale can be removed. No interest in buying books." and the older "rea, om
inte nu så sen" (retire, re-open only if he re-opens it). The retirement is
UI-only on the data side: the wishlist rows all stay, the `price` table and
its columns stay (no destructive migration), and the machine route + the
nightly runner are gone.

THE LEGS:

* ZERO PRICE BYTES on the wishlist, owner AND anonymous — the DoD pattern
  `streckpris|rea|lägga|pris|90 dagar`, case-insensitive, over the served
  bytes — asserted WITH a price row planted in the kept table, so the leg
  proves the display is GONE, not merely unfed; plus the byte-identity leg:
  the same anonymous page with and without price rows is the SAME BYTES.
* /pris ANSWERS LIKE AN UNKNOWN PATH — anonymous GET and POST take the
  guard's uniform 302 (status AND `Location` equal to a control unknown
  path); the owner's session takes the §9 404 on GET and on POST, again
  equal to the control, and the POST 404 comes AFTER the CSRF gate (so it is
  routing's answer, which is what "the route is gone" means here).
  `PRIS_DOOR_TOKEN` is INERT: arming it changes no answer.
* NOTHING OF THE FEATURE IS REACHABLE: no url rule names it, `app.pris` and
  `app.priskort` do not exist as modules, and neither do the runner and its
  state files (`scripts/pris_vakt.py`, `scripts/pris_state.py` — deleted,
  nothing else ever imported the latter). `scripts/pris_parse.py` and
  `scripts/curl_transport.py` DO still exist and import: the surviving
  /ai-rek runner is their caller (dead_code.py's citation for the keep).
* THE TABLE STANDS: `price` still answers a SELECT (0 rows) after a POST at
  the deleted route — kept as history, written by nothing.

TWO READINGS STATED, not hidden:

1. The anonymous WHOLE-PAGE zero-match leg runs on the landing `/`, and the
   /bibliotek leg asserts the wishlist SECTION. Why: the DoD pattern contains
   the substring `rea`, and MC 12551's public filter row carries the ordinary
   Swedish word "Filtrera" — a filter button is not price copy, so the
   whole-page claim belongs to the landing, which renders the SAME
   `_hyllan.html` shelf with no filter chrome (MC 12522's one-shelf rule).
2. The session csrf token is pinned to a fixed literal on the owner legs.
   `secrets.token_urlsafe` can by chance mint a body containing `rea`; a leg
   that flakes once in some thousands of runs is not a gate.

PLANTED-RED duty (each leg shown red on the pre-change tree, one mutant at a
time, sha-verified restore): with the price line restored in
`_bokkort.html` legs 1-4 go red (the DoD pattern is exactly what it renders);
with `("/pris", ...)` re-added to `auth.TOKENLESS_POSTS` + a stub route at
/pris answering 503, legs 5-7 go red (302-vs-503 and 404-vs-503); with the
DROP TABLE line added to schema.sql, the table leg goes red (OperationalError
no such table: price).
"""
import importlib.util
import re
import sqlite3

import pytest

from app import create_app
from tests.test_browse import PASSWORD, seed_shelf

# The DoD pattern, verbatim (case-insensitive). `rea` is deliberately a bare
# substring: it catches REA, rea-, -rea and the word "rea" itself.
MÖNSTER = re.compile(r"streckpris|rea|lägga|pris|90 dagar", re.IGNORECASE)

WISH_ID = 5                        # seed_shelf's wishlist row, public by ruling
WISH_ISBN = "9791234567890"        # synthetic 979-prefix, never a real isbn
WISH_TITLE = "En skatt av silver"
CSRF_FAST = "fast-csrf-token-0000"  # see reading 2
OKÄNT = "/nagot-okant-hylla"       # the control unknown path


def _app():
    app = create_app()
    app.testing = True
    return app


@pytest.fixture()
def plats(tmp_path, monkeypatch):
    """The CONFIGURED site on the synthetic shelf: wish id 5 carries an isbn
    so a price row can be planted against it, exactly as the deleted door
    used to resolve one."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    app = _app()
    client = app.test_client()
    assert client.post("/liselott/satt-loesenord",
                       data={"loesenord": PASSWORD,
                             "bekrafta": PASSWORD}).status_code == 302
    with client.session_transaction("/liselott/logga-in") as sess:
        sess["csrf"] = CSRF_FAST              # deterministic body bytes
    return tmp_path, client


def _prisrad(tmp):
    """One row in the KEPT table, written the way the DB still allows it —
    the door that used to write it is gone, so this is a hand-plant, and
    that is the whole point: data present, page silent."""
    conn = sqlite3.connect(tmp / "liselott.db")
    conn.execute(
        "INSERT INTO price (book_id, isbn, retailer, price, currency,"
        " checked_at, suspect) VALUES (?,?,?,?,'SEK',?,0)",
        (WISH_ID, WISH_ISBN, "bokus", 99, "2026-11-16T09:00:00Z"))
    conn.commit()
    conn.close()


def _radera_prisrader(tmp):
    conn = sqlite3.connect(tmp / "liselott.db")
    conn.execute("DELETE FROM price")
    conn.commit()
    conn.close()


def _antal_prisrader(tmp):
    conn = sqlite3.connect(tmp / "liselott.db")
    try:
        return conn.execute("SELECT COUNT(*) FROM price", ()).fetchone()[0]
    finally:
        conn.close()


def _utkastare(body):
    return MÖNSTER.findall(body)


# ── A. the wishlist carries ZERO price bytes, with price data in the DB ─────

def test_the_owner_wishlist_page_carries_no_price_strings(plats):
    tmp, client = plats
    _prisrad(tmp)
    r = client.get("/liselott/onska")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert WISH_TITLE in body                       # the page is really there
    assert _utkastare(body) == []                   # and carries no price
    assert "99 kr" not in body                      # belt: the planted value


def test_the_anonymous_landing_carries_no_price_strings(plats):
    tmp, _ = plats
    _prisrad(tmp)
    body = _app().test_client().get("/liselott/").get_data(as_text=True)
    assert "Att läsa" in body and WISH_TITLE in body
    assert _utkastare(body) == []


def test_the_anonymous_shelf_wishlist_section_carries_no_price_strings(plats):
    """The section the price line used to sit in, asserted as a section: the
    whole /bibliotek page carries MC 12551's filter row, whose "Filtrera"
    contains the pattern's `rea` — see reading 1."""
    tmp, _ = plats
    _prisrad(tmp)
    body = _app().test_client().get("/liselott/bibliotek").get_data(as_text=True)
    avsnitt = body[body.index("Att läsa"):]         # the LAST shelf section
    assert WISH_TITLE in avsnitt
    assert _utkastare(avsnitt) == []


def test_a_planted_price_row_changes_no_page_bytes(plats):
    """The display did not go quiet-for-now: with zero rows and with one,
    the anonymous page is the SAME BYTES, so nothing reads the kept table."""
    tmp, _ = plats
    anon = _app().test_client()
    fore = anon.get("/liselott/").data
    assert _antal_prisrader(tmp) == 0
    _prisrad(tmp)
    assert _antal_prisrader(tmp) == 1
    assert anon.get("/liselott/").data == fore


# ── B. /pris answers exactly like an unknown path ───────────────────────────

def test_pris_meets_the_uniform_302_of_an_unknown_path(plats):
    """"Route GONE" on a CONFIGURED site is NOT 404 for the anonymous
    visitor: the guard answers BEFORE routing, so an unknown extension-less
    path is the login refuse — /pris included, GET and POST alike, and
    byte-equal to the control path so enumeration learns nothing."""
    _, _ = plats
    anon = _app().test_client()
    for path in ("/liselott/pris", "/liselott" + OKÄNT):
        for ask in (anon.get, anon.post):
            r = ask(path)
            assert r.status_code == 302, (path, r.status_code)
            assert r.headers["Location"] == "/liselott/logga-in", path


def test_the_owner_meets_the_same_404_as_an_unknown_path(plats):
    """The owner's session passes the guard, so the answer is routing's: 404
    on GET, and 404 on POST too — the CSRF gate ran and passed (her token
    rode the form field), which is why this is the §9 page and not a 400.
    Same status as the control unknown path, same page."""
    tmp, client = plats
    for path in ("/liselott/pris", "/liselott" + OKÄNT):
        r = client.get(path)
        assert r.status_code == 404, path
        assert "hittas inte" in r.get_data(as_text=True), path
        p = client.post(path, data={"csrf": CSRF_FAST})
        assert p.status_code == 404, path
    assert _antal_prisrader(tmp) == 0      # nothing above wrote a price row


def test_the_door_token_env_is_inert(plats, monkeypatch):
    """`PRIS_DOOR_TOKEN` is read by NOTHING any more: armed with a value,
    the anonymous POST still takes the guard's 302 (never 503, never 401),
    so no half-open door is left behind the name."""
    _, _ = plats
    monkeypatch.setenv("PRIS_DOOR_TOKEN", "a" * 64)
    r = _app().test_client().post("/liselott/pris", data="x")
    assert r.status_code == 302, r.status_code
    assert r.headers["Location"] == "/liselott/logga-in"


# ── C. what is gone, what stayed, and what the DB still holds ───────────────

def test_no_route_and_no_app_module_names_the_feature():
    app = _app()
    assert [str(rule) for rule in app.url_map.iter_rules()
            if "pris" in str(rule)] == []
    for borta in ("app.pris", "app.priskort"):
        assert importlib.util.find_spec(borta) is None, borta


def test_the_runner_and_its_state_module_are_gone_the_parser_is_not():
    """pris_state.py had exactly ONE importer — pris_vakt.py — so the runner
    going orphaned it and it went the same way (dead_code: nothing reaches
    it). pris_parse.py and curl_transport.py are REACHED through the live
    /ai-rek runner, which is why they stayed — and the runner really is
    wired to them (its module object carries both), not merely present."""
    for borta in ("scripts.pris_vakt", "scripts.pris_state"):
        assert importlib.util.find_spec(borta) is None, borta
    for kvar in ("scripts.pris_parse", "scripts.curl_transport"):
        assert importlib.util.find_spec(kvar) is not None, kvar
    from scripts import ai_rek_pass as rp        # the caller, really wired
    assert rp.read_library.__doc__               # the reader it drives
    assert rp.pp.read_graded is not None         # THE shelf-page parser
    assert rp._curl_config is not None           # the secret-free delivery


def test_the_price_table_stands_and_nothing_writes_to_it(plats):
    """No destructive migration: the table and its columns are kept as
    history (schema.sql's RETIRED block says so). A POST in the retired
    door's own shape now 404s and stores NOTHING — the table cannot be fed
    through the app any more. The token rides the X-CSRF-Token header so the
    gate provably PASSES and the 404 is the router's, and no Origin is sent
    (§6.6: a missing Origin passes the origin rule, a foreign one would 400
    and prove nothing about the route)."""
    tmp, client = plats
    payload = ('[{"isbn":"%s","retailer":"bokus","price":99,'
               '"currency":"SEK","checked_at":"2026-11-16T09:00:00Z"}]'
               % WISH_ISBN)
    r = client.post("/liselott/pris", data=payload,
                    headers={"Content-Type": "application/json",
                             "X-CSRF-Token": CSRF_FAST})
    assert r.status_code == 404, r.status_code
    assert _antal_prisrader(tmp) == 0
    _prisrad(tmp)                                # the table still accepts one
    assert _antal_prisrader(tmp) == 1
    _radera_prisrader(tmp)
