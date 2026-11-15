"""MC 12542 (M9a-1) — the POST /pris DOOR contract (DESIGN-prisbevakning-v2
§6e, read in full, + §4 rule 4's G1 evaluator).

One JSON array in, seven aggregate counters out, zero book data echoed. The
legs below are the contract's own classes, each one named:

* ACCEPT — one fresh row for a wish: accepted 1, inserted 1, nothing rejected.
* UPSERT — the same isbn again the same day is ONE history point
           (`ux_price_isbn_day`): the second POST answers updated 1 and the
           table holds one row. Arrival order cannot move a verdict.
* rejected_shape — isbn not exactly 13 ASCII digits (12, 14, hyphens, an int),
  retailer ≠ "bokus", currency ≠ "SEK", price a float / bool / 0 / 20001 / a
  string, checked_at date-only or with an offset, a row that is not an object.
* rejected_date — stamped 3 days back or 1 h ahead: outside the CLAMPED
  window [now − 2 d, now + 5 min] (§4 rule 5, the backdate defence).
* rejected_unknown — an isbn no wish carries, INCLUDING a READ book's isbn:
  M9a's whole fetch scope is the wishlist, so a price with no wish has nowhere
  to be displayed and nowhere to be checked.
* the two budgets — body over MAX_PRIS_BODY 413s and rows over MAX_PRIS_ROWS
  400s, each naming its own number, neither touching the table.
* the envelope — no Content-Length is 411 (the F-E2 posture both other machine
  doors already hold); a payload that is not an array is a payload-shape 400.
* the posture — TOKENLESS (the runner POST carries no browser token) but never
  guardless: a foreign Origin 400s AT THE GUARD even with a valid door token,
  and every non-POST method on /pris keeps the uniform 302 (MC 12546's door
  allow is the POST method only).
* the credential (MC 12546, owner ruling 2026-11-15) — a DEDICATED DOOR
  TOKEN instead of the site password — the `X-Pris-Token` header is
  compared to the `PRIS_DOOR_TOKEN` env value inside the door, BEFORE
  any body parse. Env unset ⇒ 503 fail-closed
  for EVERY POST, owner session included, proving zero write; wrong or absent
  token ⇒ 401 in ONE uniform copy (no oracle); byte-exact, so a PREFIX of
  the real token is just another wrong key; a valid owner session rides the
  door without the token (her own tools ride the session).
* G1 — the FIRST observation is never suspect; a drop to under 2/5 of the
  latest observation strictly BEFORE the written day is; a re-ask of the SAME
  day cannot suppress the day it just confirmed (the F-b cure); exactly 60 %
  is not "more than 60 %".
* retention — one prune per accepted POST clears rows past RETENTION_DAYS.

PLANTED-RED (the DoD's one-per-new-gate rule). Every gate this card added was
run once against a build with THAT gate removed, and every one of them went
red on its own leg (transcripts on MC 12542's trail). Named here because a
check that has never failed is not a check: the clamp (`pass` where the two
window returns are, red as rejected_date=0/accepted=1), the price bounds (red
as a raw CHECK-constraint 500 — the pre-validation is what keeps the table's
own constraints from ever answering the door), the wishlist resolve, the byte
budget, the row budget, the Content-Length rule (in
tests/test_ingest_vocab.py's sweep), and the door's TOKENLESS membership in
auth.TOKENLESS_POSTS (red as the CSRF page's 400: the exemption is load-
bearing, not decoration).
MC 12546 plants one red per NEW gate, the same rule (transcript
`.tmp/m9a1b-planted-red.md`, host-local; the tree restored to shipped bytes
before commit): the 503 fail-closed (the unarmed branch made to `return
None` — the env-unset legs go red as accepted rows written), the 401 refusal
(the token compare made to `return None` — the wrong/absent legs go red as
200), the byte-exact compare (`compare_digest` → `startswith` — the prefix
leg goes red as 200), the session carve (its branch removed — the owner
leg goes red as 401) and the POST-only guard allow (`_is_pris_door` widened
to every method — the GET leg goes red as the door's own answer, not the
guard's 302).
"""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app import pris
from app import create_app
from tests.test_browse import PASSWORD, seed_shelf

WISH_ISBN = "9789173710107"        # seed_shelf's wish (id 5), given an isbn here
READ_ISBN = "9789173710015"        # seed_shelf's rated read row: a price, no wish
DOOR_CRED = "syntetisk-dorr-979"          # the fixture credential (fixture-only)
NU = datetime.now(timezone.utc).replace(microsecond=0)


def stamp(when):
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def row(isbn=WISH_ISBN, price=99, retailer="bokus", currency="SEK", when=None):
    return {"isbn": isbn, "retailer": retailer, "price": price,
            "currency": currency, "checked_at": stamp(when or NU)}


def _site(tmp_path, monkeypatch, token=DOOR_CRED):
    """The configured site on the synthetic shelf, the door ARMED with
    `token` (None = env DELETED — the disarmed posture MC 12546 ships by
    default). The env goes in via monkeypatch, the idiom every env-driven
    leg here uses. Returns (app, the owner-session client that set the
    password — §6.1 signs her in on the way)."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    if token is None:
        monkeypatch.delenv("PRIS_DOOR_TOKEN", raising=False)
    else:
        monkeypatch.setenv("PRIS_DOOR_TOKEN", token)
    seed_shelf(tmp_path / "liselott.db")
    with sqlite3.connect(tmp_path / "liselott.db") as c:
        c.execute("UPDATE book SET isbn13 = ? WHERE id = 5", (WISH_ISBN,))
    app = create_app()
    app.testing = True
    owner = app.test_client()
    assert owner.post("/liselott/satt-loesenord",
                      data={"loesenord": PASSWORD,
                            "bekrafta": PASSWORD}).status_code == 302
    return app, owner


class Runner:
    """The MC 12546 caller posture: a FRESH client with no session whose
    every POST carries the door token — the daily runner, NOT Liselott.
    `.raw` is the same client without the stamp (the negative legs),
    `.owner` the session that configured the site (her legs, no token)."""

    def __init__(self, client, owner):
        self.raw = client
        self.owner = owner
        self._client = client

    def post(self, path, headers=None, **kw):
        merged = dict(headers or {})
        merged["X-Pris-Token"] = DOOR_CRED
        return self._client.post(path, headers=merged, **kw)


@pytest.fixture()
def dorren(tmp_path, monkeypatch):
    """The configured site on the synthetic shelf with the door ARMED. The
    returned client IS the runner (token on every POST, zero session): the
    door's real caller since MC 12546 — the legs below ride it exactly as
    production will."""
    app, owner = _site(tmp_path, monkeypatch)
    return tmp_path, Runner(app.test_client(), owner)


def priser(tmp):
    with sqlite3.connect(tmp / "liselott.db") as c:
        return c.execute("SELECT isbn, price, checked_at, suspect, book_id"
                         " FROM price ORDER BY checked_at").fetchall()


# ── accept + the day upsert ─────────────────────────────────────────────────
def test_door_accepts_one_fresh_wish_price(dorren):
    tmp, client = dorren
    r = client.post("/liselott/pris", json=[row()])
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json() == {"accepted": 1, "inserted": 1, "updated": 0,
                            "suspect": 0, "rejected_unknown": 0,
                            "rejected_shape": 0, "rejected_date": 0}
    assert priser(tmp) == [(WISH_ISBN, 99, stamp(NU), 0, 5)]   # book_id resolved HERE


def test_door_upserts_a_same_day_re_ask_into_one_point(dorren):
    """The dedup is the UNIQUE day index, not a SELECT-then-INSERT: a manual
    re-run re-asks and overWRITES today's row — one history point per isbn per
    day, whatever order the two POSTs arrive in."""
    tmp, client = dorren
    earlier = row(price=99, when=NU - timedelta(hours=6))
    later = row(price=85, when=NU)
    assert client.post("/liselott/pris", json=[earlier]).get_json()["inserted"] == 1
    assert client.post("/liselott/pris", json=[later]).get_json()["updated"] == 1
    assert priser(tmp) == [(WISH_ISBN, 85, stamp(NU), 0, 5)]


def test_door_response_echoes_no_book_data(dorren):
    """§6e: the response is AGGREGATES. A body that carried a title or an isbn
    would turn the runner's credential into a shelf reader."""
    _, client = dorren
    body = client.post("/liselott/pris", json=[row()]).get_data(as_text=True)
    assert json.loads(body).keys() == {"accepted", "inserted", "updated",
                                       "suspect", "rejected_unknown",
                                       "rejected_shape", "rejected_date"}
    assert WISH_ISBN not in body and "skatt" not in body.lower()


# ── rejected_shape ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("bad", [
    {"isbn": "978917371010", "price": 99},          # 12 digits
    {"isbn": "97891737101077", "price": 99},         # 14
    {"isbn": "978-9173710107", "price": 99},         # hyphens are not the key
    {"isbn": 9789173710107, "price": 99},            # an int is not the shape
    {"isbn": WISH_ISBN, "price": 99.0},              # a float that looks integral
    {"isbn": WISH_ISBN, "price": True},
    {"isbn": WISH_ISBN, "price": "99"},
    {"isbn": WISH_ISBN, "price": 0},
    {"isbn": WISH_ISBN, "price": 20001},
    {"isbn": WISH_ISBN, "price": None},
    {"isbn": WISH_ISBN, "price": 99, "retailer": "adlibris"},
    {"isbn": WISH_ISBN, "price": 99, "retailer": None},
    {"isbn": WISH_ISBN, "price": 99, "currency": "EUR"},
    {"isbn": WISH_ISBN, "price": 99, "checked_at": "2026-11-15"},        # no time
    {"isbn": WISH_ISBN, "price": 99, "checked_at": "2026-11-15T12:00:00+01:00"},
    {"isbn": WISH_ISBN, "price": 99, "checked_at": "2026-02-31T12:00:00Z"},
    {"isbn": WISH_ISBN, "checked_at": None},
])
def test_door_rejects_shape_without_touching_the_table(dorren, bad):
    tmp, client = dorren
    full = {"isbn": WISH_ISBN, "retailer": "bokus", "price": 99,
            "currency": "SEK", "checked_at": stamp(NU)}
    body = client.post("/liselott/pris",
                       json=[dict(full, **bad)]).get_json()
    assert body["rejected_shape"] == 1, bad
    assert body["accepted"] == 0 and body["rejected_date"] == 0
    assert priser(tmp) == []


def test_door_rejects_a_row_that_is_not_an_object(dorren):
    tmp, client = dorren
    body = client.post("/liselott/pris", json=["9789173710107"]).get_json()
    assert body == {"accepted": 0, "inserted": 0, "updated": 0, "suspect": 0,
                    "rejected_unknown": 0, "rejected_shape": 1,
                    "rejected_date": 0}
    assert priser(tmp) == []


# ── rejected_date: the clamped window ───────────────────────────────────────
@pytest.mark.parametrize("when", [
    NU - timedelta(days=3),                # the backdate the clamp refuses
    NU - timedelta(days=2, seconds=90),    # one minute PAST the edge
    NU + timedelta(hours=1),               # a runner whose clock runs ahead
])
def test_door_refuses_a_stamp_outside_the_clamped_window(dorren, when):
    """§4 rule 5: history may only arrive stamped today or the last two days,
    so a holder of the credential cannot poison the 90-day floor from six
    months back. The named residual (a ≤ 2-day backdate is still possible)
    rides with the rule — it is stated in §6e, not fixed here."""
    tmp, client = dorren
    body = client.post("/liselott/pris", json=[row(when=when)]).get_json()
    assert body["rejected_date"] == 1 and body["accepted"] == 0
    assert priser(tmp) == []


@pytest.mark.parametrize("avstand", [timedelta(days=-2) + timedelta(seconds=60),
                                      timedelta(minutes=5)])
def test_window_edges_are_inside_the_window(dorren, avstand):
    """The bounds are inclusive on both ends — a leg so the reject above is
    not accidentally a whole-window reject.

    The stamp is sampled from the CLOCK inside the leg, not from the module's
    `NU`: the door judges the edge from its OWN `now` at request time, and a
    constant sampled at import drifts across the edge while the suite runs. A
    first version of this leg pinned 20 s of margin and went red in a 150-second
    full-suite run — the margin was the bug, not the door (the OUTSIDE legs
    drift the safe way: age only pushes a stamp further out, so those keep the
    module constant). 60 s of slack on the old edge is what a fixture + request
    can never burn through."""
    tmp, client = dorren
    nu = datetime.now(timezone.utc).replace(microsecond=0)
    body = client.post("/liselott/pris",
                       json=[row(when=nu + avstand)]).get_json()
    assert body["accepted"] == 1
    assert len(priser(tmp)) == 1


# ── rejected_unknown: the wishlist is the whole fetch scope ─────────────────
def test_door_refuses_an_isbn_no_wish_carries(dorren):
    """The isbn is a SYNTHETIC 979-prefixed one, chosen by instrument against
    the list `scripts/exposure_check.py` reads as its oracle. The first cut of
    this leg used a plausible-looking 978-91 number that turned out to BE a
    real wishlist ISBN and turned the exposure gate red — the tracked universe
    is what the gate greps, so it only spoke after the commit. Plausible is not
    synthetic: 979 is a prefix this diary never carries, and the check is the
    list, never taste."""
    tmp, client = dorren
    body = client.post("/liselott/pris",
                       json=[row(isbn="9790000000001")]).get_json()
    assert body["rejected_unknown"] == 1 and body["accepted"] == 0
    assert priser(tmp) == []


def test_door_refuses_a_read_books_isbn(dorren):
    """M9a tracks the wishlist only. A read book's isbn resolves to a book row
    — and is still refused, because nothing may ever display that price and
    the fetch scope has no page for it."""
    tmp, client = dorren
    body = client.post("/liselott/pris", json=[row(isbn=READ_ISBN)]).get_json()
    assert body["rejected_unknown"] == 1 and body["accepted"] == 0
    assert priser(tmp) == []


# ── the two budgets + the envelope ──────────────────────────────────────────
def test_door_refuses_a_body_over_the_byte_budget(dorren):
    tmp, client = dorren
    rows = [row(price=100 + i) for i in range(700)]      # ≈73 kB of JSON
    body = json.dumps(rows, separators=(",", ":")).encode()
    assert len(body) > pris.MAX_PRIS_BODY
    r = client.post("/liselott/pris", data=body,
                    content_type="application/json")
    assert r.status_code == 413, r.get_data(as_text=True)
    assert str(pris.MAX_PRIS_BODY) in r.get_data(as_text=True)
    assert "Ingen prisrad är lagrad" in r.get_data(as_text=True)
    assert priser(tmp) == []


def test_door_refuses_more_rows_than_the_budget(dorren):
    """Under the BYTE budget on purpose: this is the row count speaking, and
    it names the count it saw."""
    tmp, client = dorren
    rows = [row(price=100 + i) for i in range(pris.MAX_PRIS_ROWS + 1)]
    body = json.dumps(rows, separators=(",", ":")).encode()
    assert len(body) <= pris.MAX_PRIS_BODY
    r = client.post("/liselott/pris", data=body,
                    content_type="application/json")
    assert r.status_code == 400, r.get_data(as_text=True)
    assert str(len(rows)) in r.get_data(as_text=True)
    assert str(pris.MAX_PRIS_ROWS) in r.get_data(as_text=True)
    assert priser(tmp) == []


def test_door_refuses_a_payload_that_is_not_an_array(dorren):
    """A single object is not a list of one: the payload shape is the door's
    first word, and it 400s before any row is judged."""
    tmp, client = dorren
    r = client.post("/liselott/pris", json=row())
    assert r.status_code == 400
    assert "array" in r.get_data(as_text=True)
    assert priser(tmp) == []


def test_door_answers_empty_array_with_zero_counters(dorren):
    """A quiet day is a 200 of zeroes, not an error — the runner's daily POST
    may legitimately carry nothing it managed to read."""
    _, client = dorren
    assert client.post("/liselott/pris", json=[]).get_json() == {
        "accepted": 0, "inserted": 0, "updated": 0, "suspect": 0,
        "rejected_unknown": 0, "rejected_shape": 0, "rejected_date": 0}


# ── the posture: tokenless, never guardless ─────────────────────────────────
def test_get_on_pris_still_meets_the_uniform_302(tmp_path, monkeypatch):
    """MC 12546's method rule, §6.4 sweep material: the guard's door allow
    is the POST method ONLY, so an anonymous GET /pris — even CARRYING the
    valid door token — keeps the uniform 302 the guard gives every private
    path. A key that opens a write door never widens the read surface."""
    app, _owner = _site(tmp_path, monkeypatch)
    r = app.test_client().get("/liselott/pris",
                              headers={"X-Pris-Token": DOOR_CRED})
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/logga-in")


def test_door_needs_no_browser_token_but_refuses_a_foreign_origin(dorren):
    """§6.6's machine posture + MC 12546's DoD row 3: the runner's POST
    carries the door token and NO browser CSRF token (the door sits in
    TOKENLESS_POSTS); a MISSING Origin passes, a foreign one 400s — and it
    400s AT THE GUARD WITH A VALID DOOR TOKEN, so a cross-site POST never
    reaches the compare whatever key it rides. The exemption is TOKENLESS,
    not guardless and not origin-free."""
    _, client = dorren
    r = client.post("/liselott/pris", json=[],
                    headers={"Origin": "https://evil.example"})
    assert r.status_code == 400, "a valid door token must not outvote Origin"
    assert client.post("/liselott/pris", json=[],
                       headers={"Origin": "http://localhost"}).status_code == 200


# ── MC 12546: the door's OWN credential — dedicated token, never the password
def test_valid_door_token_without_any_session_is_accepted(dorren):
    """The point of M9a-1b: the runner is a STRANGER WITH A KEY. No session
    cookie on the request, the token on the header ⇒ the row lands; and the
    answer hands out NO session of its own (Set-Cookie absent — the door
    answers counters, it does not mint logins)."""
    tmp, client = dorren
    r = client.post("/liselott/pris", json=[row()])
    assert r.status_code == 200 and r.get_json()["accepted"] == 1
    assert "Set-Cookie" not in r.headers
    assert priser(tmp) == [(WISH_ISBN, 99, stamp(NU), 0, 5)]


def test_wrong_and_missing_door_tokens_answer_the_same_401(dorren):
    """Wrong ⇒ 401, absent ⇒ 401, and the two answers are BYTE-EQUAL — the
    copies carry no oracle for a probe to walk (this leg IS the uniform-
    copy claim). Neither writes a row."""
    tmp, client = dorren
    wrong = client.raw.post("/liselott/pris", json=[row()],
                            headers={"X-Pris-Token": DOOR_CRED + "-fel"})
    absent = client.raw.post("/liselott/pris", json=[row()])
    assert (wrong.status_code, absent.status_code) == (401, 401)
    assert wrong.get_data() == absent.get_data()
    assert priser(tmp) == []


def test_door_compares_the_token_byte_exact_a_prefix_is_not_enough(dorren):
    """The constant-time posture at BEHAVIOUR level (the shipped compare is
    hmac.compare_digest over UTF-8 bytes, app/pris.py): a strict PREFIX of
    the real token is just another wrong key — a compare that accepted what
    a probe already knew would hand it the suffix one byte at a time. The
    full value passes right after, so the refusal is the prefix, not the
    fixture."""
    tmp, client = dorren
    r = client.raw.post("/liselott/pris", json=[row()],
                        headers={"X-Pris-Token": DOOR_CRED[:6]})
    assert r.status_code == 401
    assert priser(tmp) == []
    assert client.post("/liselott/pris",
                       json=[row()]).get_json()["accepted"] == 1


def test_owner_session_post_needs_no_door_token(dorren):
    """The MC 12546 carve, kept EXPLICIT: the owner's own tools ride her
    session (a valid session already IS write access to the whole shelf —
    re-gating it at the door would guard nothing but the copy), so her POST
    with NO token header at all is accepted."""
    tmp, client = dorren
    r = client.owner.post("/liselott/pris", json=[row()])
    assert r.status_code == 200 and r.get_json()["accepted"] == 1
    assert priser(tmp) == [(WISH_ISBN, 99, stamp(NU), 0, 5)]


def test_door_answers_503_and_writes_nothing_when_the_env_is_unset(
        tmp_path, monkeypatch):
    """Fail-closed IS the shipped default: no PRIS_DOOR_TOKEN on the server
    means the door is DISARMED — 503, before the envelope rules and before
    any body parse, and the table proves the counters never ran: a payload
    of one perfectly legal row wrote NOTHING."""
    app, _owner = _site(tmp_path, monkeypatch, token=None)
    r = app.test_client().post("/liselott/pris", json=[row()])
    assert r.status_code == 503, r.get_data(as_text=True)
    assert priser(tmp_path) == []


def test_the_disarmed_door_503s_the_owner_session_too(tmp_path, monkeypatch):
    """The claim is LITERAL — 503 for every POST (MC 12546): an unset env
    never means open — even the session that owns the site meets the disarmed
    door's 503 while no credential is wired, and writes nothing."""
    _app, owner = _site(tmp_path, monkeypatch, token=None)
    r = owner.post("/liselott/pris", json=[row()])
    assert r.status_code == 503
    assert priser(tmp_path) == []


# ── G1 (§4 rule 4): the door is the named evaluator ─────────────────────────
def test_g1_first_observation_is_never_suspect(dorren):
    """No prev ⇒ no suppression: the ghost that never existed cannot silence
    the day it would have been read off."""
    _, client = dorren
    assert client.post("/liselott/pris", json=[row(price=9)]).get_json()["suspect"] == 0


def test_g1_flags_a_drop_past_sixty_percent(dorren):
    tmp, client = dorren
    client.post("/liselott/pris", json=[row(price=100, when=NU - timedelta(days=1))])
    body = client.post("/liselott/pris", json=[row(price=39)]).get_json()
    assert (body["accepted"], body["suspect"]) == (1, 1)     # stored, FLAGGED
    assert priser(tmp)[-1][3] == 1


def test_g1_exactly_sixty_percent_is_not_past_sixty_percent(dorren):
    """The boundary is named as a STRICT drop: 100 → 40 is exactly 60 % off
    and is a price, not a ghost."""
    _, client = dorren
    client.post("/liselott/pris", json=[row(price=100, when=NU - timedelta(days=1))])
    assert client.post("/liselott/pris", json=[row(price=40)]).get_json()["suspect"] == 0


def test_g1_compares_the_day_before_never_the_same_day(dorren):
    """The F-b cure: prev is the latest observation STRICTLY before the written
    row's day, so today's re-ask (100 then 39, both today) can never suppress
    the badge day it just confirmed. The row is still stored with its price."""
    tmp, client = dorren
    client.post("/liselott/pris", json=[row(price=100, when=NU - timedelta(hours=8))])
    body = client.post("/liselott/pris", json=[row(price=39)]).get_json()
    assert (body["accepted"], body["suspect"], body["updated"]) == (1, 0, 1)
    assert priser(tmp) == [(WISH_ISBN, 39, stamp(NU), 0, 5)]


@pytest.mark.parametrize("ordning", ["front", "back"])
def test_g1_is_order_independent_within_one_post(dorren, ordning):
    """A restated yesterday plus a new today in the SAME payload, posted in
    BOTH orders: the stored series — prices AND suspect flags — is identical
    either way. Today's 39 is judged against the yesterday the payload itself
    carries (100 ⇒ a >60 % drop ⇒ flagged), never against whatever the table
    happened to hold before the restatement landed."""
    tmp, client = dorren
    bakåt = row(price=100, when=NU - timedelta(days=1))
    idag = row(price=39)
    client.post("/liselott/pris",
                json=[idag, bakåt] if ordning == "front" else [bakåt, idag])
    assert priser(tmp) == [(WISH_ISBN, 100, stamp(NU - timedelta(days=1)), 0, 5),
                           (WISH_ISBN, 39, stamp(NU), 1, 5)]


# ── retention: one prune per accepted POST ──────────────────────────────────
def test_door_prunes_rows_past_the_retention_window(dorren):
    """730 days, backup.py's KEEP posture, ONE DELETE per accepted POST — not
    a job and not a timer. The old row is planted by hand because the door's
    own window would (and does, above) refuse a stamp that old."""
    tmp, client = dorren
    gammalt = stamp(NU - timedelta(days=pris.RETENTION_DAYS + 1))
    with sqlite3.connect(tmp / "liselott.db") as c:
        c.execute("INSERT INTO price (isbn, book_id, retailer, price,"
                  " checked_at) VALUES (?,5,'bokus',99,?)", (WISH_ISBN, gammalt))
    assert len(priser(tmp)) == 1
    assert client.post("/liselott/pris", json=[row()]).get_json()["accepted"] == 1
    assert len(priser(tmp)) == 1
