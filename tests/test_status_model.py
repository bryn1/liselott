"""MC 12733 (M12 W1) — the status model: "Läser nu" + "Avbruten".

The domain widens to ('read','wishlist','reading','aborted') (R1 — stored
tokens English; the Swedish words live in books.STATUS_WORDS AND display
through it: since the DA-verdict-w1 F1 fix round `group_for_shelf` reads its
section labels THROUGH the map — the original wave shipped the map beside the
display, zero consumers, an overstatement this header shared). THE LAW this
file owns, per PLAN-M12 §1 REV 2:

* four doors, all in app/onska.py (R6): las-nu (wishlist|aborted → reading,
  no date no year), avbryt (reading → aborted, the 0 sentinel keeps its
  meaning), /las widened (wishlist|reading → read WITH a date — a read row
  still 400s, `read → read` never happens), and the existing grading flip
  (routes.py, through seed.mark_read). `read → anything` never happens.
* the ONE wish law `status == 'wishlist'` at every wish site (F-A) — the
  wide `!= 'read'` is retired at books.PUBLIC_SET_SQL,
  books.group_for_shelf, the /onska page's list reads, and filtrering.narrow.
* the PUBLIC posture, ruled in the same wave (F-E): a status word NEVER
  paints in anonymous bytes; the new-status rows that can reach the public
  shelf are the RATED ones (MC 12501: rated ⇒ public) — a rated 'aborted'
  row (the F-E card) AND, contra §1's retired "a rated READING row is
  unreachable by construction" wording, a rated 'reading' row, reachable
  through the real doors (bundle wishlist+rating, then las-nu; DA-verdict-w1
  F2) — each rendered as a PLAIN bokkort card under its shelf year (the 0
  sentinel → "Utan år"), facing ?betyg=/?ar= like any read row; the
  unrated reading/aborted rows are invisible (same unrated rule). A RATED
  wishlist row stays q-only under the params (the ratified wishlist
  exemption) — over-inclusive, stated in the LEDGER, behaviour unchanged.
* owner shelf sections [Läser nu][year ↓][Utan år][Avbruten][Att läsa],
  empty groups never render; the public grouping carries no new label
  (owner_view rides the ONE view point, routes._hylldata).

THE FIXTURES: `shelf` is tests/test_browse's synthetic shelf (ids 1–5) plus
row 9 "Tolv månars tystnad" (read, unrated, year 0 — the NO_YEAR repair
class, F-B; LEGAL at the base commit, so the three PINS run there green);
`hylla` adds the three widened-domain rows: 6 "Springlådan" (reading,
unrated, year 0), 7 "Brottslingen" (aborted, unrated, year 0), 8
"Fjordbreven" (aborted, RATED 3 — the F-E public card; invented titles,
MC 12523 posture). At the base commit `hylla` itself raises (the old CHECK
refused the new tokens) — which is the red-first fact: the domain arrived
with this wave. All titles are invented synthetic (MC 12523).

RED-first at 55f19ce (.tmp-w1/): the door legs (las-nu/avbryt 404, /las on a
reading row 400), the mark_read source-set leg, the grouping legs and the
public-render legs all fail on base. THREE LEGS ARE PINS — green at base,
named per §7's pin-vs-plant clause, each with its named mutant run beside
the green transcripts: test_the_new_doors_keep_guard_and_csrf (mutant: the
door joins auth.TOKENLESS_POSTS → the anon 302 becomes a 400/302-wrong — the
run shows the leg RED on the guard-drop),
test_the_read_year_repair_survives_the_narrowing (F-B; mutant: naive
`row[0] not in ("wishlist","reading"): return` retires the year repair),
and test_bundle_never_transitions_the_new_tokens (mutant: widening
bundle.py's refuse-list admits 'reading' → the POST answers 200).

THE FIX ROUND (DA-verdict-w1, cycle 2) adds TWO legs, both green against the
pre-fix tree (pin-adjacent — they pin behaviour the wave already shipped, so
per §7's pin-vs-plant law each names its MUTANT instead of a red-first
transcript): test_the_status_words_map_is_the_rendered_copy (F1 — mutant:
hardcode a divergent label in group_for_shelf beside the map → the
map-derived heading check goes RED; on the pre-fix tree that mutant stayed
GREEN, which IS F1) and test_the_rated_reading_row_is_a_plain_public_card
(F2 — mutant: PUBLIC_SET_SQL narrowed back with `AND status <> 'reading'`
→ the anon 200 goes RED; painting a status word on the public card → the
wordless checks go RED). Mutant transcripts: .tmp-w1-c2/ in the wave's
audit dir.
"""
import re
import sqlite3
from datetime import date, datetime, timezone

import pytest

from app import create_app
from app.books import STATUS_WORDS, group_for_shelf
from tests.test_browse import PASSWORD, seed_shelf
from tests.test_seed_routes import bundle_bytes, line

# (id, title, rating, status) — the three new-status rows MC 12733 adds.
NY_RADER = [
    (6, "Springlådan", None, "reading"),
    (7, "Brottslingen", None, "aborted"),
    (8, "Fjordbreven", 3, "aborted"),
]
READING = ("Springlådan",)
ABORTED_UNRATED = ("Brottslingen",)
ABORTED_RATED = "Fjordbreven"
NOYEAR_READ = 9                      # id in the `shelf` fixture (legal at base)
NY_NOYEAR_TITLE = "Tolv månars tystnad"

PRIVATE_NEW_IDS = (6, 7, 9)
PUBLIC_IDS = (1, 2, 4, 5, 8)          # rated 1/2/4 + wishlist 5 + RATED aborted 8

IARE = datetime.now(timezone.utc).year


@pytest.fixture()
def shelf(tmp_path, monkeypatch):
    """The synthetic shelf PLUS row 9 only (a legal `read`/year-0 row — the
    NO_YEAR class exists at the base commit too), the password set, and the
    two postures (the MC 12501 fixture idiom). The three PINS run HERE,
    green at 55f19ce, because their legs must not depend on the widened
    domain; every other leg runs in `hylla`."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    conn = sqlite3.connect(tmp_path / "liselott.db")
    now = "2026-11-20T00:00:00Z"
    conn.execute(
        "INSERT INTO book (id, title, year, read_year, date_read, rating,"
        " format, status, book_key, created, updated)"
        " VALUES (?,?,NULL,0,NULL,NULL,'bok','read',?,?,?)",
        (NOYEAR_READ, NY_NOYEAR_TITLE, f"key-{NOYEAR_READ}", now, now))
    conn.commit()
    conn.close()
    app = create_app()
    app.testing = True
    owner = app.test_client()
    assert owner.post("/liselott/satt-loesenord",
                      data={"loesenord": PASSWORD,
                            "bekrafta": PASSWORD}).status_code == 302
    anon_app = create_app()
    anon_app.testing = True
    return tmp_path, owner, anon_app.test_client()


@pytest.fixture()
def hylla(shelf):
    """The widened shelf: the three new-status rows ride on top of `shelf`.
    AT THE BASE COMMIT this fixture itself raises — the old CHECK refuses
    'reading'/'aborted' — which IS the red-first fact the domain arrived
    with this wave (transcript .tmp-w1/red-status-model.txt)."""
    tmp = shelf[0]
    conn = sqlite3.connect(tmp / "liselott.db")
    now = "2026-11-20T00:00:00Z"
    for bid, title, rating, status in NY_RADER:
        conn.execute(
            "INSERT INTO book (id, title, year, read_year, date_read, rating,"
            " format, status, book_key, created, updated)"
            " VALUES (?,?,NULL,0,NULL,?,'bok',?,?,?,?)",
            (bid, title, rating, status, f"key-{bid}", now, now))
    conn.commit()
    conn.close()
    return shelf


def token(client):
    with client.session_transaction("/liselott/logga-in") as sess:
        return sess["csrf"]


def rad(db_path, book_id, cols):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(f"SELECT {', '.join(cols)} FROM book WHERE id = ?",
                            (book_id,)).fetchone()
    finally:
        conn.close()


def _ids(html):
    return {int(m) for m in re.findall(r'href="/liselott/bok/(\d+)"', html)}


def _r(title, status, read_year=0, date_read=None):
    """A row shaped like load_books hands the grouping (the ONE shape the
    view passes; test_shelf_grouping's unit idiom)."""
    return {"title": title, "status": status, "read_year": read_year,
            "date_read": date_read}


def _headings(html):
    return re.findall(r"<h2[^>]*>([^<]+)</h2>", html)


# ── the doors: the valid transitions (all four RED at 55f19ce) ───────────────
def test_las_nu_flips_a_wish_to_laser_nu(hylla):
    """wishlist → reading: the flip is the WHOLE transition — no date, no
    year (naming a date is what /las means; the wish's 0 sentinel keeps its
    meaning, R6)."""
    tmp, owner, _ = hylla
    r = owner.post("/liselott/onska/5/las-nu", data={"csrf": token(owner)})
    assert r.status_code == 302
    assert r.headers["Location"] == "/liselott/bok/5"
    assert rad(tmp / "liselott.db", 5, ["status", "date_read", "read_year"]) \
        == ("reading", None, 0)


def test_las_nu_resumes_an_aborted_book(hylla):
    tmp, owner, _ = hylla
    r = owner.post("/liselott/onska/7/las-nu", data={"csrf": token(owner)})
    assert r.status_code == 302
    assert rad(tmp / "liselott.db", 7, ["status"])[0] == "reading"


def test_avbryt_flips_laser_nu_to_avbruten(hylla):
    tmp, owner, _ = hylla
    r = owner.post("/liselott/onska/6/avbryt", data={"csrf": token(owner)})
    assert r.status_code == 302
    status, year = rad(tmp / "liselott.db", 6, ["status", "read_year"])
    assert status == "aborted" and year == 0     # the sentinel keeps meaning


def test_las_admits_a_reading_row_and_dates_it(hylla):
    """R6: `reading → read` reuses the ONE existing dated door — the gate
    widens from `!= "wishlist"` to admit 'reading'; mark_read owns the flip
    and the sentinel year, the door names today's date."""
    tmp, owner, _ = hylla
    r = owner.post("/liselott/onska/6/las", data={"csrf": token(owner)})
    assert r.status_code == 302
    status, datum, year = rad(tmp / "liselott.db", 6,
                              ["status", "date_read", "read_year"])
    assert status == "read"
    assert datum == date.today().isoformat()
    assert year == IARE                            # the 0 sentinel is replaced


# ── the doors: invalid + repeat (§5.11's never, pinned per leg) ──────────────
def test_read_row_has_no_status_door(shelf):
    """read → anything never happens: las-nu, avbryt AND the /las door all
    keep refusing a read row (`read → read` never happens either)."""
    tmp, owner, _ = shelf
    for action in ("las-nu", "avbryt", "las"):
        r = owner.post(f"/liselott/onska/1/{action}",
                       data={"csrf": token(owner)})
        assert r.status_code == 400, action
        assert rad(tmp / "liselott.db", 1, ["status"])[0] == "read"


def test_a_wish_cannot_be_aborted(shelf):
    tmp, owner, _ = shelf
    r = owner.post("/liselott/onska/5/avbryt", data={"csrf": token(owner)})
    assert r.status_code == 400
    assert rad(tmp / "liselott.db", 5, ["status"])[0] == "wishlist"


def test_repeat_flips_are_400(hylla):
    """las-nu is pinned to 400-on-repeat (the plan's idempotent-or-400
    choice): a second click meets the door, it does not silently re-flip."""
    tmp, owner, _ = hylla
    assert owner.post("/liselott/onska/6/avbryt",
                      data={"csrf": token(owner)}).status_code == 302
    assert owner.post("/liselott/onska/6/avbryt",
                      data={"csrf": token(owner)}).status_code == 400
    assert owner.post("/liselott/onska/5/las-nu",
                      data={"csrf": token(owner)}).status_code == 302
    assert owner.post("/liselott/onska/5/las-nu",
                      data={"csrf": token(owner)}).status_code == 400


def test_aborted_is_not_admitted_by_the_las_door(hylla):
    """aborted → read must run THROUGH las-nu first (resume, then date it) —
    the /las gate admits only wishlist and reading (R6)."""
    tmp, owner, _ = hylla
    r = owner.post("/liselott/onska/7/las", data={"csrf": token(owner)})
    assert r.status_code == 400
    assert rad(tmp / "liselott.db", 7, ["status"])[0] == "aborted"


def test_the_new_doors_keep_guard_and_csrf(shelf):
    """PIN (green at 55f19ce — the doors are not in PUBLIC_READ_* and not in
    TOKENLESS_POSTS, and the standing _csrf_gate answers every owner POST):
    an anonymous POST meets the guard's uniform 302, an owner POST without
    the csrf field meets the 400. Red-proof plants beside the green
    transcripts: a door added to auth.TOKENLESS_POSTS / a door in the public
    read lists turns the 302 legs RED; a door reading no csrf turns the 400
    leg RED."""
    _, owner, anon = shelf
    for action in ("las-nu", "avbryt"):
        r = anon.post(f"/liselott/onska/5/{action}", data={})
        assert r.status_code == 302, action
        assert r.headers["Location"] == "/liselott/logga-in", action
        assert owner.post(f"/liselott/onska/5/{action}", data={}).status_code \
            == 400, action
        # unknown ids keep the route's own 404 (at the base commit this half
        # passes vacuously — no route is a 404 too; §7 names it inside the PIN).
        assert owner.post(f"/liselott/onska/9999/{action}",
                          data={"csrf": token(owner)}).status_code == 404


# ── mark_read's source set (R4) + the year-repair PIN (F-B) ──────────────────
def test_grading_an_aborted_book_keeps_it_aborted(hylla):
    """R4: DNF + a rating is a truthful pair — grading is still a flip-to-read
    ONLY for wishlist/reading rows; an 'aborted' row keeps its status AND its
    0 sentinel, the rating lands. RED at 55f19ce: mark_read flipped ANY row
    it was handed except (read, year)."""
    tmp, owner, _ = hylla
    r = owner.post("/liselott/betyg/7", data={"betyg": "2",
                                              "csrf": token(owner)})
    assert r.status_code == 302
    assert rad(tmp / "liselott.db", 7, ["status", "read_year", "rating"]) \
        == ("aborted", 0, 2)


def test_the_read_year_repair_survives_the_narrowing(shelf):
    """PIN (F-B, green at 55f19ce): the NO_YEAR repair class — grading a
    (read, 0) row back-fills the year TODAY (the seed's 0 sentinel group) —
    the narrowing must NOT retire it: the row stays read, read_year becomes
    this year, no date is invented. Red-proof mutant, run beside the green
    transcripts: the naive narrowing (`status not in ('wishlist','reading')
    → return`) early-returns on this class and the leg goes RED."""
    tmp, owner, _ = shelf
    r = owner.post(f"/liselott/betyg/{NOYEAR_READ}",
                   data={"betyg": "4", "csrf": token(owner)})
    assert r.status_code == 302
    status, year, datum = rad(tmp / "liselott.db", NOYEAR_READ,
                              ["status", "read_year", "date_read"])
    assert status == "read" and year == IARE and datum is None


# ── the ONE wish law on the /onska page (F-A) ─────────────────────────────────
def test_onska_lists_the_wishlist_only(hylla):
    """`status != 'read'` was "anything but read" — after the widened domain
    a läser nu / avbruten row on "Att läsa" with the old button is exactly
    the fragmentation F-A names. The page's list AND its length are the wish
    set: one wishlist row; the re-rendered form-error page lives by the same
    law (it is the same ONE read, app/onska.py::onskelistan)."""
    _, owner, _ = hylla
    sida = owner.get("/liselott/onska")
    assert "En skatt av silver" in sida.text
    for borta in READING + ABORTED_UNRATED + (ABORTED_RATED,):
        assert borta not in sida.text
    assert sida.text.count('class="onska-rad"') == 1
    fel = owner.post("/liselott/onska/lagg-till",
                     data={"titel": " ", "forfattare": "Någon",
                           "csrf": token(owner)})
    assert fel.status_code == 400
    assert "Springlådan" not in fel.text and "Brottslingen" not in fel.text
    assert fel.text.count('class="onska-rad"') == 1


# ── the shelf's sections (owner order; public order carries no new word) ─────
def test_owner_shelf_sections_order_new_first(hylla):
    _, owner, _ = hylla
    assert _headings(owner.get("/liselott/bibliotek").text) == [
        "Läser nu", "2026", "2025", "2024", "Utan år", "Avbruten", "Att läsa"]


def test_the_status_words_map_is_the_rendered_copy(hylla):
    """F1 (DA-verdict-w1, fix round): STATUS_WORDS is not a word BESIDE the
    display — group_for_shelf reads its section labels THROUGH the map, so
    map and rendered copy cannot drift. Half one: the owner shelf's
    headings ARE the map's words (a hardcoded divergent label goes RED
    here — pre-fix, with zero map consumers, that mutant stayed GREEN:
    that was F1). Half two: the map still says the plan's Swedish (a map
    word edit goes RED here). Half three: the bok.html action-row buttons
    are §9's fixed ACTION copy (verbs, not status words) — pinned beside
    the map here so one edit screen shows both vocabularies."""
    assert STATUS_WORDS["reading"] == "Läser nu"
    assert STATUS_WORDS["aborted"] == "Avbruten"
    assert STATUS_WORDS["wishlist"] == "Att läsa"
    _, owner, _ = hylla
    assert _headings(owner.get("/liselott/bibliotek").text) == [
        STATUS_WORDS["reading"], "2026", "2025", "2024", "Utan år",
        STATUS_WORDS["aborted"], STATUS_WORDS["wishlist"]]
    for book_id, knapp in ((5, "Jag läser den nu"), (6, "Läst nu"),
                           (6, "Avbryt"), (7, "Jag läser den nu igen")):
        assert knapp in owner.get(f"/liselott/bok/{book_id}").text, knapp


def test_group_for_shelf_owner_sections():
    grupper = group_for_shelf([
        _r("A", "read", 2026), _r("B", "read", 2025), _r("C", "read"),
        _r("D", "wishlist"), _r("E", "reading"), _r("F", "aborted")],
        owner_view=True)
    assert [label for label, _ in grupper] == [
        "Läser nu", 2026, 2025, "Utan år", "Avbruten", "Att läsa"]
    # empty groups never render (the _hyllan law): drop the rows, drop them.
    utan_ny = group_for_shelf([_r("A", "read", 2026), _r("D", "wishlist")],
                              owner_view=True)
    assert [label for label, _ in utan_ny] == [2026, "Att läsa"]


def test_group_for_shelf_public_sections_carry_no_new_word():
    """F-E ruling, at the ONE view point: the public view (the FLAG'S
    DEFAULT — a caller that forgets to opt in gets the calm public posture,
    never a new word) paints NO status label — a rated aborted (or any)
    new-status row groups by its shelf year like a read row (the 0 sentinel
    lands it under "Utan år"), still the plain bokkort card the template
    already makes."""
    rader = [_r("A", "read", 2026), _r("B", "read", 2025), _r("C", "read"),
             _r("D", "wishlist"), _r("E", "reading"), _r("F", "aborted")]
    for grupper in (group_for_shelf(rader),
                    group_for_shelf(rader, owner_view=False)):
        labels = [label for label, _ in grupper]
        assert labels == [2026, 2025, "Utan år", "Att läsa"]
        assert "Läser nu" not in labels and "Avbruten" not in labels
        by_label = dict(grupper)
        assert [b["title"] for b in by_label["Utan år"]] == ["C", "E", "F"]


def test_shelf_month_is_the_guarded_month():
    """The Året primitive (W2), born with the guarded shelf_year idiom: a
    real date gives its month, everything unusable (None, empty, malformed,
    an impossible month) is the 0 sentinel — never a crash. RED at the base
    commit as an AttributeError: the primitive is born in this wave."""
    from app.books import shelf_month
    assert shelf_month(_r("X", "read", date_read="2026-03-14")) == 3
    assert shelf_month(_r("X", "read", date_read="2026-1-5")) == 1
    for datum in (None, "", "2026-13-01", "2026-00-10", "hösten 2026"):
        assert shelf_month(_r("X", "read", date_read=datum)) == 0, datum


# ── the public render: the F-E ruling and the leak legs ──────────────────────
def test_anon_never_names_the_unrated_new_status_rows(hylla):
    """The leak legs (PUBLIC_SET_SQL left wide would surface these — the
    named leak plant goes RED here): the unrated reading/aborted rows and
    the yearless unrated read row are NOWHERE in anonymous bytes, and the
    words "Läser nu"/"Avbruten" never appear at all — owner copy only."""
    _, _, anon = hylla
    for path in ("/liselott/", "/liselott/bibliotek"):
        body = anon.get(path).text
        assert _ids(body) == set(PUBLIC_IDS), path
        for borta in READING + ABORTED_UNRATED + ("Tolv månars tystnad",):
            assert borta not in body, (path, borta)
        assert "Läser nu" not in body and "Avbruten" not in body, path


def test_the_rated_aborted_row_is_a_plain_public_card(hylla):
    """The F-E ruling's two halves: the unrated new rows meet the login
    refuse (indistinguishable from nonexistent ids); the RATED aborted row
    IS public (rated ⇒ public, MC 12501) and renders as a plain bokkort/bok
    page — no status word, no owner door."""
    _, _, anon = hylla
    for book_id in PRIVATE_NEW_IDS:
        assert anon.get(f"/liselott/bok/{book_id}").status_code == 302
    sida = anon.get("/liselott/bok/8")
    assert sida.status_code == 200
    assert "Fjordbreven" in sida.text
    assert "Avbruten" not in sida.text and "Läser nu" not in sida.text
    assert "/redigera/" not in sida.text           # MC 12497: no door on public
    shelf = anon.get("/liselott/bibliotek").text
    assert "Fjordbreven" in shelf.split("</form>")[-1]


def test_the_rated_reading_row_is_a_plain_public_card(hylla):
    """F2 (DA-verdict-w1, fix round): §1's "a rated READING row is
    unreachable by construction" is FALSE — the machine door accepts a
    RATED WISHLIST line (bundle.py validates rating 1–5 and its refuse
    list KEEPS 'wishlist'), and las-nu then flips that very row to
    'reading' with its rating intact. The behaviour already stands inside
    the MC 12501 ruling (rated ⇒ public, plain card); this leg PINS the
    class end-to-end through the REAL doors. Mutants: narrowing
    PUBLIC_SET_SQL with `AND status <> 'reading'` turns the anon 200 RED;
    painting any status word on the public card turns the wordless checks
    RED (both run in .tmp-w1-c2/; the leg is GREEN at the cycle-1 tree
    `1b0b4cb` — a pin there, not a red-first leg; MC 12734 W2 wording carry,
    DA-verdict-w1-c2 G1: at the wave's BASE `55f19ce` the file does not even
    exist, so "at base" named the wrong tree)."""
    tmp, owner, anon = hylla
    r = owner.post("/liselott/bundle", data=bundle_bytes(line(
        book_key="kRatedReading", title="Strömbrytaren", status="wishlist",
        rating=4, read_year=0)), content_type="application/octet-stream")
    assert r.status_code == 200
    conn = sqlite3.connect(tmp / "liselott.db")
    try:
        book_id, status, rating = conn.execute(
            "SELECT id, status, rating FROM book WHERE book_key = ?",
            ("kRatedReading",)).fetchone()
    finally:
        conn.close()
    assert (status, rating) == ("wishlist", 4)       # the door took the pair
    assert owner.post(f"/liselott/onska/{book_id}/las-nu",
                      data={"csrf": token(owner)}).status_code == 302
    assert rad(tmp / "liselott.db", book_id, ["status", "rating"]) \
        == ("reading", 4)                             # rated reading: REAL
    sida = anon.get(f"/liselott/bok/{book_id}")
    assert sida.status_code == 200                    # rated ⇒ public
    assert "Strömbrytaren" in sida.text
    for word in ("Avbruten", "Läser nu", "Läst nu"):
        assert word not in sida.text, word            # wordless plain card
    assert "/redigera/" not in sida.text              # MC 12497: no door
    assert 'action="/liselott/onska' not in sida.text
    assert "Strömbrytaren" in anon.get(
        "/liselott/bibliotek").text.split("</form>")[-1]


def test_the_rated_aborted_row_faces_the_params(hylla):
    """A row that carries real data faces the params (filtrering.py's
    narrowing narrows to `== 'wishlist'` for the exemption): its rating
    narrows like any read row's, and its 0-sentinel year means EVERY ?ar=
    lawfully excludes it (the same way yearless read rows are excluded)."""
    _, _, anon = hylla
    def shelf(query):
        return anon.get(f"/liselott/bibliotek?{query}").text.split("</form>")[-1]
    assert "Fjordbreven" in shelf("betyg=3")
    assert "Fjordbreven" not in shelf("betyg=4")
    for ar in (2024, 2025, 2026):
        assert "Fjordbreven" not in shelf(f"ar={ar}"), ar
    assert "Fjordbreven" in shelf("q=fjordbreven")
    assert "Fjordbreven" not in shelf("q=silver")


# ── the bok page's status action row (owner surface, §1 UX) ──────────────────
def test_owner_bok_page_carries_the_status_action_row(hylla):
    """One small action row keyed on the row's status, inside the existing
    inloggad() posture (the anon bok bytes are pinned untouched in
    tests/test_edit_path); calm Swedish buttons, csrf on every form; a read
    row carries NO row at all (§5.11)."""
    _, owner, _ = hylla
    onska = owner.get("/liselott/bok/5").text
    assert 'action="/liselott/onska/5/las-nu"' in onska
    assert "Jag läser den nu" in onska and 'name="csrf"' in onska
    reading = owner.get("/liselott/bok/6").text
    assert 'action="/liselott/onska/6/las"' in reading       # dated door, legal here
    assert 'action="/liselott/onska/6/avbryt"' in reading
    assert "Läst nu" in reading and "Avbryt" in reading
    aborted = owner.get("/liselott/bok/7").text
    assert 'action="/liselott/onska/7/las-nu"' in aborted
    assert "Jag läser den nu igen" in aborted
    read_row = owner.get("/liselott/bok/1").text
    assert "/onska/" not in read_row and "Jag läser den" not in read_row


# ── the machine doors stay closed to the new vocabulary (R7) ─────────────────
def test_bundle_never_transitions_the_new_tokens(shelf):
    """PIN (green at 55f19ce — bundle.py's refuse-list (None,'read',
    'wishlist') predates M12, §7 names it): a bundle must NEVER transition,
    the widened CHECK does not widen the door. Red-proof mutant, run beside
    the green transcripts: admitting 'reading'/'aborted' into the refuse-
    list makes this POST answer 200 (and stores a new-status row) — RED."""
    tmp, owner, _ = shelf
    for n, status in enumerate(("reading", "aborted")):
        r = owner.post("/liselott/bundle", data=bundle_bytes(
            line(book_key=f"kNy{n}", title=f"Ny {status}", status=status)),
            content_type="application/octet-stream")
        assert r.status_code == 400, status
    conn = sqlite3.connect(tmp / "liselott.db")
    try:
        assert conn.execute("SELECT COUNT(*) FROM book WHERE book_key LIKE"
                            " 'kNy%'").fetchone()[0] == 0
    finally:
        conn.close()
