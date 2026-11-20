"""MC 12735 (M12 W3) — the quiet draw: GET /slump + the ONE entry link on
/onska (PLAN-M12 REV 2 §4; R3: the draw is NOT annual, so it lives with its
data — the wishlist's read face inside app/onska.py, the module that already
owns the wishlist's UI: one module for the wishlist, no second door beside it).

THE CONTRACT this file owns:
* THE POOL IS THE WISHLIST, BY LAW (F-A): the rows are `status == 'wishlist'`
  read through the ONE loader `books.load_books`, id-sorted (the loader's own
  order law — a draw must be reproducible, and reproducibility starts with a
  deterministic pool). `random.choice` over that pool answers through a
  module-level `random` seam the tests monkeypatch (the house seam idiom:
  monkeypatch.setattr on the module, like test_ai_rek's `skapa_onska` and
  test_add's `pacer` — no new mechanism). No dismissal bookkeeping, no
  history: no state to keep calm honest (§4).
* ONE calm bok card via the shelf's own `_bokkort` macro + a quiet "Smaka på
  en annan" redraw link to /slump + a link back to /onska. An EMPTY wishlist
  renders ONE quiet line ("Önskelistan är tom.") — never a dead card, never
  a redraw link drawing at nothing.
* THE F-A COUNT LEG: the /onska entry link ("{count} böcker i listan · Slumpa
  fram en bok", count through the house `number_and_word`) carries a count
  that EQUALS the draw's pool size and the /onska list length — all three
  read against SQL. The failure the old wide wording hid (a wide list, a
  narrow pool, "count > 0" yet the draw answers "tom") cannot exist: one
  predicate, `status == 'wishlist'`, at all three sites.
* owner-only BY GUARD: /slump rides NO auth.PUBLIC_READ list — an anonymous
  GET answers the guard's uniform 302, byte-identical to the private /sok
  posture (§4's public-surface proof, the /aret precedent).
* the slash rule rides the ai_rek.py/aret.py precedent: /slump/ answers the
  page itself, same bytes, zero redirects.
* EXACTLY ONE entry point: the link at the head of /onska. The nav gains NO
  link (a leg pins the word "Slumpa" absent from every nav page) — R3's
  "entered from ONE quiet link" is a shape law, and shape laws get tests.

THE FIXTURE (invented synthetic titles, MC 12523 posture): tests/test_browse's
seed_shelf (ids 1–5 — wishlist "En skatt av silver" id 5) plus four rows this
file owns: 6 "Sjöngeln" (wishlist), 7 "Månradet" (wishlist), 8 "Barkhyllan"
(reading) and 9 "Granvakteln" (aborted). §7's law BINDS the fixture: it
CARRIES reading + aborted rows or the pool mutant `status != 'read'` is
invisible — the containment leg below is exactly where that mutant must go
RED. Pool ids are [5, 6, 7] in id order; the fold-title order of the same
rows is [5, 7, 6], so the named-draw leg (draw index 1) renders "Sjöngeln"
ONLY if the pool is ID-sorted — a title-sorted pool answers "Månradet" and
goes RED.

RED-FIRST at base `1930ea8` (.tmp-w3/red-first-w3.txt): the draw legs, the
empty-copy leg, the entry-link legs and the slash leg are RED there (no
/slump route; the seam name `random` does not even exist on onska; the
entry link is not painted). ONE LEG IS A PIN (§7's pin-vs-plant clause) —
green at base, the guard posture predates the route:
`test_anon_get_slump_is_the_uniform_guard_posture`, named MUTANT: "/slump"
added to auth.PUBLIC_READ_PATHS turns the anon 302 into a 200
(.tmp-w3/mutant-slump-public.txt). The pool mutant (`status != 'read'`) runs
in a copy tree, never in the repo: .tmp-w3/mutant-pool-wide.txt — containment
RED. The count mutant (the /onska list widened back to `!= 'read'` beside the
narrow pool — F-A's exact failure) reddens the count leg:
.tmp-w3/mutant-count-wide.txt.
"""
import random
import re
import sqlite3

import pytest

from app import create_app, onska
from app.db import init_db
from tests.test_browse import PASSWORD, seed_shelf

# (id, title, year, read_year, date_read, rating, format, status)
NYA_RADER = [
    (6, "Sjöngeln", None, 0, None, None, "bok", "wishlist"),
    (7, "Månradet", None, 0, None, None, "bok", "wishlist"),
    (8, "Barkhyllan", 2021, 0, None, None, "bok", "reading"),
    (9, "Granvakteln", 2019, 0, None, None, "bok", "aborted"),
]
POOL_IDS = [5, 6, 7]                      # the wishlist, id order (SQL-checked)
BAIT_IDS = [8, 9]                         # reading + aborted: never drawable
BAIT_TITLES = ("Barkhyllan", "Granvakteln")
SEED = 20261120
N_DRAWS = 60                              # the containment run
_NR_RE = re.compile(r'href="/liselott/bok/(\d+)"')


class _Val:
    """The test's half of the draw seam: a CHOOSER with a known answer.
    `onska` reaches the draw through the module name `random`, so the leg
    hands it one of these (the house monkeypatch seam — the stdlib module
    object is never patched)."""

    def __init__(self, at):
        self.at = at

    def choice(self, rows):
        return rows[self.at]


def _ins(conn, bid, title, year, read_year, date_read, rating, fmt, status):
    now = "2026-11-20T00:00:00Z"
    conn.execute(
        "INSERT INTO book (id, title, year, read_year, date_read, rating,"
        " format, status, book_key, created, updated)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (bid, title, year, read_year, date_read, rating, fmt, status,
         f"key-{bid}", now, now))


def _app(tmp_path):
    app = create_app()
    app.testing = True
    return app


def _owner(app):
    client = app.test_client()
    assert client.post("/liselott/satt-loesenord", data={
        "loesenord": PASSWORD, "bekrafta": PASSWORD}).status_code == 302
    return client


def _sql_wishlist(tmp):
    conn = sqlite3.connect(tmp / "liselott.db")
    try:
        return [r[0] for r in conn.execute(
            "SELECT id FROM book WHERE status = 'wishlist' ORDER BY id")]
    finally:
        conn.close()


@pytest.fixture()
def hylla(tmp_path, monkeypatch):
    """The baited pool fixture: seed_shelf (ids 1–5) + rows 6–9 — three
    wishes, one reading, one aborted. Owner session + a second app on the
    SAME state dir for the anonymous posture."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    conn = sqlite3.connect(tmp_path / "liselott.db")
    for row in NYA_RADER:
        _ins(conn, *row)
    conn.commit()
    conn.close()
    app = _app(tmp_path)
    return tmp_path, _owner(app), _app(tmp_path).test_client()


@pytest.fixture()
def utan_onskan(tmp_path, monkeypatch):
    """A shelf with READ, READING and ABORTED rows and NO wish at all: the
    empty draw must answer from the POOL predicate being empty, not from a
    whole empty table (a `!= 'read'` pool would find two rows here)."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    conn = sqlite3.connect(tmp_path / "liselott.db")
    init_db(conn)
    _ins(conn, 1, "Kustlandet", 2001, 2026, "2026-04-03", 4, "bok", "read")
    _ins(conn, 2, "Barkhyllan", 2021, 0, None, None, "bok", "reading")
    _ins(conn, 3, "Granvakteln", 2019, 0, None, None, "bok", "aborted")
    conn.commit()
    conn.close()
    return tmp_path, _owner(_app(tmp_path))


# ── the draw ────────────────────────────────────────────────────────────────
def test_seeded_draw_renders_the_named_wishlist_card(hylla, monkeypatch):
    """Draw index 1 of the ID-SORTED pool [5,6,7] is id 6 "Sjöngeln"; in
    fold-title order index 1 would be "Månradet" — so this leg pins the
    pool's order AND the named row AND the calm page shape in one draw:
    ONE bokkort, the redraw link to /slump, the way back to /onska, and the
    wishlist's own nav link marked (the page reached from there)."""
    _, owner, _ = hylla
    monkeypatch.setattr(onska, "random", _Val(1))
    sida = owner.get("/liselott/slump")
    assert sida.status_code == 200
    assert "<title>Slumpa fram en bok — Liselotts bokhylla</title>" in sida.text
    assert sida.text.count('class="bok-kort"') == 1     # ONE calm card (§4)
    assert 'class="titel">Sjöngeln</span>' in sida.text  # the ID order, §4
    assert "Månradet" not in sida.text                   # not title-sorted
    assert "En skatt av silver" not in sida.text
    assert 'href="/liselott/slump">Smaka på en annan</a>' in sida.text
    assert 'href="/liselott/onska"' in sida.text
    assert 'aria-current="page">Önskelista</a>' in sida.text


def test_n_runs_stay_inside_the_wishlist(hylla, monkeypatch):
    """THE CONTAINMENT LEG (§4): 60 draws through a real seeded `Random` (the
    seam is seed-injectable — the stream is reproducible, so this run is the
    run, not a hope). Every drawn id must sit inside the SQL wishlist set,
    the reading/aborted bait must NEVER paint, and the pool's three wishes
    must ALL appear (the pool is neither narrower nor wider than the law).
    The pool mutant `status != 'read'` puts ids 8 and 9 in reach and goes
    RED here — the fixture carries them for exactly this (§7's law)."""
    tmp, owner, _ = hylla
    monkeypatch.setattr(onska, "random", random.Random(SEED))
    dragen = []
    for _ in range(N_DRAWS):
        text = owner.get("/liselott/slump").get_data(as_text=True)
        hit = _NR_RE.findall(text)
        assert len(hit) == 1, text[:200]
        dragen.append(int(hit[0]))
        for titel in BAIT_TITLES:
            assert titel not in text
    assert set(dragen) <= set(_sql_wishlist(tmp)) <= set(POOL_IDS)
    assert set(dragen) == set(POOL_IDS)          # every wish reachable
    conn = sqlite3.connect(tmp / "liselott.db")
    try:
        bait = [r[0] for r in conn.execute(
            "SELECT id FROM book WHERE status IN ('reading','aborted')"
            " ORDER BY id")]
    finally:
        conn.close()
    assert bait == BAIT_IDS                       # the bait is REAL, not prose
    assert not set(dragen) & set(BAIT_IDS)        # never drawn


def test_empty_wishlist_is_one_quiet_line(utan_onskan):
    """§4: empty pool, ONE calm line — no card, no redraw link drawing at
    nothing ("never a dead card"), and /onska dangles no entry link when the
    count is 0 (F-A: the count rides the pool, and a 0-count link would
    promise a draw that answers "tom")."""
    _, owner = utan_onskan
    sida = owner.get("/liselott/slump")
    assert sida.status_code == 200
    assert "<p class=\"tom-state\">Önskelistan är tom.</p>" in sida.text
    assert 'class="bok-kort"' not in sida.text
    assert "Smaka på en annan" not in sida.text
    assert 'href="/liselott/onska"' in sida.text       # the way back stands
    assert "Slumpa fram en bok" not in owner.get("/liselott/onska").text


# ── the ONE entry link (F-A: count == pool == list, all against SQL) ────────
def test_onska_entry_link_count_is_pool_is_list_length(hylla):
    """The head link reads "3 böcker i listan · Slumpa fram en bok" and the
    3 closes against SQL THREE times over: wishlist rows == count in the
    link == rendered list rows. The bait rows (reading + aborted) are on the
    shelf RIGHT NOW: the retired wide wording would answer 5 — the count
    mutant (the page's list widened to `!= 'read'` beside the narrow pool)
    goes RED on exactly this equality (.tmp-w3/mutant-count-wide.txt).
    The same leg pins the SHAPE: the word "Slumpa" rides ONE link on the
    wishlist page and appears in NO nav anywhere."""
    tmp, owner, _ = hylla
    sida = owner.get("/liselott/onska").text
    hit = re.findall(r'href="([^"]+)">(\d+) böcker i listan ·'
                     r' Slumpa fram en bok</a>', sida)
    assert hit == [("/liselott/slump", "3")], hit
    assert sida.count('class="onska-rad"') == 3
    assert _sql_wishlist(tmp) == POOL_IDS
    for path in ("/liselott/", "/liselott/bibliotek", "/liselott/aret"):
        assert "Slumpa" not in owner.get(path).text, path


def test_one_wish_says_en_bok(tmp_path, monkeypatch):
    """number_and_word (the house count agreement) over the single-wish
    shelf: "1 bok i listan" — a Swedish page must not say "1 böcker" while
    calmly counting. (Fixture: plain seed_shelf — exactly one wish row.)"""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    owner = _owner(_app(tmp_path))
    sida = owner.get("/liselott/onska").text
    assert 'href="/liselott/slump">1 bok i listan · Slumpa fram en bok</a>' \
        in sida


# ── the posture and the shape ────────────────────────────────────────────────
def test_the_slash_spelling_is_the_same_page(hylla, monkeypatch):
    """The ai_rek.py/aret.py precedent: the explicit slash rule answers the
    page itself — same endpoint, same bytes, zero redirects. The draw seam is
    pinned to a constant choice so the two GETs carry the SAME card (the
    redraw link is the page's own, not the router's)."""
    _, owner, _ = hylla
    monkeypatch.setattr(onska, "random", _Val(0))
    r = owner.get("/liselott/slump/")
    assert r.status_code == 200
    assert r.data == owner.get("/liselott/slump").data


def test_anon_get_slump_is_the_uniform_guard_posture(hylla):
    """§4's public-surface proof, the /aret leg mirrored: /slump rides NO
    auth.PUBLIC_READ_PATHS/_PREFIXES, so the guard's uniform 302 answers —
    byte-for-byte the refuse every private surface gives, in the prefixed,
    the bare and the slashed shape. THIS LEG IS A PIN (§7): green at base,
    the posture predates the route; named mutant = "/slump" added to
    auth.PUBLIC_READ_PATHS (the 302 becomes a 200) —
    .tmp-w3/mutant-slump-public.txt."""
    _, _, anon = hylla
    r = anon.get("/liselott/slump")
    assert r.status_code == 302
    assert r.headers["Location"] == "/liselott/logga-in"
    sok = anon.get("/liselott/sok")
    assert r.data == sok.data                         # the SAME uniform bytes
    assert r.headers["Location"] == sok.headers["Location"]
    for path in ("/liselott/slump/", "/slump"):
        r = anon.get(path)
        assert r.status_code == 302, path
        assert r.headers["Location"] == "/liselott/logga-in", path
