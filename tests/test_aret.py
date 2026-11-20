"""MC 12734 (M12 W2) — the Året page: F3's annual recap + F5's quiet stats on
ONE owner page (PLAN-M12 REV 2 §2+§3; ONE page, ONE nav link, per R2).

THE CONTRACT this file owns:
* "Årets läsning <år>" (§2): the count, the rated snitt (one decimal, comma,
  sv style), toppar (rating 5, title order), the ljudbok count, the notes
  count — all over the OWNER's `read` rows only; aborted/reading rows NEVER
  enter a year's numbers (§2's exclusion; the bait rows below make it test).
* "Genom åren" (§3): one line per year present in the READ rows, newest
  first; yearless read rows ride as "Utan år: N", the wishlist as
  "Önskelistan: N", and W1's statuses as their own non-zero lines. THE F-I
  CLOSING SUMS: year lines + "Utan år" == the read count; + wishlist +
  reading + aborted == the whole table — the leg reads the NUMBERS BACK OFF
  THE RENDERED PAGE and closes them against SQL, never against itself.
* per-month lines within the selected year via books.shelf_month; monthless
  rows as ONE "Utan datum" count.
* ?ar= rides filtrering.parse (R5): invalid == absent (the page answers
  byte-identical to the no-param page); a VALID year she never read in is
  ONE quiet line — never a zero scoreboard.
* owner-only by guard: /aret is not in auth.PUBLIC_READ_PATHS/_PREFIXES, so
  an anonymous GET answers the guard's uniform 302, byte-identical to the
  private /sok posture (§2's public-surface proof).
* the calm contract (NEVER-DO §3-8/9): the words "förra året", "mål",
  "streak" and "prestige" never render, and the page carries no chart.
* base.html gained EXACTLY ONE new nav link ("Året"), inside the
  inloggad-gated header; the imported byte pins prove the anon surface
  cannot move, and PIN_OWNER moved IN THIS COMMIT with truthful history
  beside the value (plan §6 W2: one new nav link, nothing else).

THE FIXTURE (invented synthetic titles, MC 12523 posture): tests/test_browse's
seed_shelf (ids 1–5) plus seven rows this file owns (ids 6–12). HAND-COMPUTED
for 2026 (the default: the newest year present): the READ rows are "Goda
natten Agda" (5, bok, 2026-10-29, notes) + "Vargsol" (5, ljudbok, 2026-02-18)
→ "Du läste 2 böcker under 2026."; snitt 5,0; toppar Goda natten Agda och
Vargsol; 1 ljudbok; 1 med anteckningar; månader "februari: 1, oktober: 1".
THE BAIT (§7's law: the fixture carries a RATED aborted row or the recap-math
mutant cannot bite): "Myrstacken" (aborted, RATED 3) and "Springlådan"
(reading) BOTH carry read_year 2026 — a recap that grouped the year by year
WITHOUT the status filter would answer "3 böcker" and snitt 4,3. 2025: 2
böcker, snitt 4,0; 2024: 3 böcker, snitt 3,5 (rated rows 3 och 4 — a .5 snitt
exercises the decimal comma); 2023: 1 bok, no rated line. Utan år: 1,
Önskelistan: 1, Läser nu: 1, Avbruten: 1 → 2+2+3+1+1 == 9 read == SQL;
9+1+1+1 == 12 == the whole table.

RED-FIRST at base `48abe41` (.tmp-w2/red-first-w2.txt): every leg that reads
the new page is RED there (no /aret route, no nav link, owner pins un-moved).
TWO LEGS ARE PINS — green at base, named per §7's pin-vs-plant clause, each
with its named MUTANT (transcripts beside them under .tmp-w2/):
`test_anon_get_aret_is_the_uniform_guard_posture` (the 302 posture predates
the route; mutant: adding "/aret" to auth.PUBLIC_READ_PATHS turns the anon
302 into a 200) and `test_anon_bytes_cannot_move` (the imported anon pins;
plant: the nav link painted OUTSIDE the inloggad() block moves the landing
bytes). The fix-round pins of W1 stay untouched by this wave.
"""
import re
import sqlite3

import pytest

from app import create_app
from tests.test_browse import PASSWORD, seed_shelf
# Reuse, never re-derive: the pin instrument, the fixture the pins were
# measured on, and the SEALED anon pins this wave may not touch.
from tests.test_public_filter import (  # noqa: F401  (konfigurerad = fixture)
    FORM_ROW, PIN_LANDING, PIN_OWNER, PIN_SHELF, _pin, konfigurerad)

# (id, title, year, read_year, date_read, rating, format, status, notes)
NYA_RADER = [
    (6, "Vargsol", 2024, 2026, "2026-02-18", 5, "ljudbok", "read", None),
    (7, "Tyst i Tived", 2021, 0, None, None, "bok", "read", None),
    (8, "Kustboken", 2019, 2025, None, 4, "bok", "read", "Bärande läsning."),
    (9, "Myrstacken", 2020, 2026, None, 3, "bok", "aborted", None),
    (10, "Springlådan", 2023, 2026, None, None, "bok", "reading", None),
    (11, "Hällelden", 1999, 2023, "2023-07-04", None, "bok", "read", None),
    (12, "Skuggören", 2018, 2024, "2024-09-12", 4, "bok", "read", None),
]

# §7's negative copy pin: these words never render on the page.
FORBUDDA_ORD = ("förra året", "mål", "streak", "prestige")


def _antal(tmp, sql):
    conn = sqlite3.connect(tmp / "liselott.db")
    try:
        return conn.execute(sql).fetchone()[0]
    finally:
        conn.close()


def _linjer(text):
    """The genom-åren rows as plain strings — the section is text-only by
    design (calm §9), so one <li> is one readable line."""
    return re.findall(r"<li>([^<>]+)</li>", text)


@pytest.fixture()
def areta(tmp_path, monkeypatch):
    """The hand-computed table (ids 1–12, docstring), the password set, and
    the two postures — the MC 12501 fixture idiom the whole suite speaks."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    conn = sqlite3.connect(tmp_path / "liselott.db")
    now = "2026-11-20T00:00:00Z"
    for (bid, title, year, read_year, date_read, rating, fmt, status,
         notes) in NYA_RADER:
        conn.execute(
            "INSERT INTO book (id, title, year, read_year, date_read, rating,"
            " format, status, book_key, notes, created, updated)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (bid, title, year, read_year, date_read, rating, fmt, status,
             f"key-{bid}", notes, now, now))
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


# ── §2: the recap, to the digit ─────────────────────────────────────────────
def test_default_page_is_the_hand_computed_recap(areta):
    _, owner, _ = areta
    sida = owner.get("/liselott/aret")
    assert sida.status_code == 200
    assert "<title>Året — Liselotts bokhylla</title>" in sida.text
    assert "Årets läsning 2026" in sida.text          # the newest year, default
    assert "Du läste 2 böcker under 2026." in sida.text
    assert "2 av dem fick betyg, i snitt 5,0." in sida.text   # decimal comma
    assert "Fem stjärnor: Goda natten Agda och Vargsol." in sida.text
    assert "Varav 1 ljudbok." in sida.text
    assert "1 hade anteckningar." in sida.text


def test_recap_excludes_aborted_and_reading(areta):
    """§2's exclusion, baited on purpose: "Myrstacken" (aborted, RATED 3) and
    "Springlådan" (reading) carry read_year 2026, so the naive year-only
    math answers "3 böcker" and snitt 4,3 — the named recap-math mutant IS
    that math (.tmp-w2/mutant-recap-math.txt)."""
    _, owner, _ = areta
    sida = owner.get("/liselott/aret").text
    assert "Du läste 2 böcker under 2026." in sida
    assert "3 böcker under 2026" not in sida
    assert "i snitt 4,3" not in sida
    assert "2026 · 2 böcker · snitt 5,0" in sida       # the history line too
    assert "Myrstacken" not in sida and "Springlådan" not in sida
    # ...and their honest lines: the tails of §3, not a silent merge.
    assert "Avbruten: 1" in sida and "Läser nu: 1" in sida


def test_ar_switches_the_year(areta):
    _, owner, _ = areta
    sida = owner.get("/liselott/aret?ar=2025")
    assert "Årets läsning 2025" in sida.text
    assert "Du läste 2 böcker under 2025." in sida.text
    assert "2 av dem fick betyg, i snitt 4,0." in sida.text
    # 2025 has no five and no ljudbok: the lines are simply not there.
    assert "Fem stjärnor" not in sida.text
    assert "Varav" not in sida.text
    assert "november: 1, Utan datum: 1" in sida.text   # the month line, §3


def test_invalid_ar_is_absent(areta):
    """R5's law through filtrering.parse: a value that is not four digits is
    the SAME as no value — byte-identical, never an error page."""
    _, owner, _ = areta
    base = owner.get("/liselott/aret")
    assert base.status_code == 200 and "Årets läsning 2026" in base.text
    base = base.data
    assert owner.get("/liselott/aret?ar=abc").data == base
    assert owner.get("/liselott/aret?ar=202").data == base
    assert owner.get("/liselott/aret?ar=20267").data == base


def test_empty_year_is_one_quiet_line(areta):
    """A VALID year she never read in: one calm sentence, no scoreboard of
    zeros (§2). The history below keeps its own bytes (§3: the section is
    the whole shelf's, not the selected year's)."""
    _, owner, _ = areta
    sida = owner.get("/liselott/aret?ar=2019")
    assert "Årets läsning 2019" in sida.text
    assert "Du läste inga böcker under 2019." in sida.text
    for part in ("i snitt", "Fem stjärnor", 'class="manader"'):
        assert part not in sida.text, part
    assert "Genom åren" in sida.text


# ── §3: the quiet stats ─────────────────────────────────────────────────────
def test_genom_aren_lines_newest_first(areta):
    _, owner, _ = areta
    linjer = _linjer(owner.get("/liselott/aret").text)
    assert linjer == [
        "2026 · 2 böcker · snitt 5,0",
        "2025 · 2 böcker · snitt 4,0",
        "2024 · 3 böcker · snitt 3,5",
        "2023 · 1 bok",
        "Utan år: 1",
        "Önskelistan: 1",
        "Läser nu: 1",
        "Avbruten: 1",
    ]
    # A year with no rated row carries NO snitt — silence, never a zero.
    assert "2023 · 1 bok · snitt" not in owner.get("/liselott/aret").text


def test_closing_sums_close_on_the_rendered_page(areta):
    """THE F-I LEG (PLAN-M12 §3, DA-verdict-plan-c2 row F-I): the year lines
    + "Utan år" == the read count, and read + wishlist + reading + aborted ==
    the whole table — the numbers come OFF THE RENDERED PAGE and close
    against SQL. (The fixture is not the 724-row shape; the law is the
    closure, computed from THIS fixture per the W2 row.)"""
    tmp, owner, _ = areta
    linjer = _linjer(owner.get("/liselott/aret").text)
    siffror = {}
    for line in linjer:
        m = (re.search(r"· (\d+) b(?:ok|öcker)", line)
             or re.search(r": (\d+)$", line))
        n = int(m.group(1))
        name = line.split(" · ")[0].split(": ")[0]
        siffror[name] = n
    ar_sum = sum(siffror[f"20{y}"] for y in ("26", "25", "24", "23"))
    lasta = ar_sum + siffror["Utan år"]
    assert lasta == _antal(tmp, "SELECT COUNT(*) FROM book"
                                " WHERE status = 'read'")
    total = (lasta + siffror["Önskelistan"] + siffror["Läser nu"]
             + siffror["Avbruten"])
    assert total == _antal(tmp, "SELECT COUNT(*) FROM book")
    assert (ar_sum, lasta, total) == (8, 9, 12)


def test_manader_and_utan_datum(areta):
    """§3: per-month counts via books.shelf_month, calendar order, monthless
    rows as ONE "Utan datum" count (the sum of the parts is the year)."""
    _, owner, _ = areta
    assert 'class="manader">februari: 1, oktober: 1<' in \
        owner.get("/liselott/aret").text
    assert 'class="manader">mars: 1, september: 1, Utan datum: 1<' in \
        owner.get("/liselott/aret?ar=2024").text


def test_calm_copy_no_comparisons_or_charts(areta):
    """NEVER-DO §3-8/9 as a machine: no comparison words, no chart markup —
    the page counts what she read and stops there."""
    _, owner, _ = areta
    for path in ("/liselott/aret", "/liselott/aret?ar=2024"):
        sida = owner.get(path).text
        assert "Årets läsning" in sida                 # the real page, not a 404
        sida = sida.casefold()
        for ord_ in FORBUDDA_ORD:
            assert ord_ not in sida, (path, ord_)
        assert "<svg" not in sida and "<canvas" not in sida


# ── the ONE new nav link, and the byte law around it ────────────────────────
def test_nav_carries_exactly_one_new_link(areta):
    _, owner, _ = areta
    for path in ("/liselott/", "/liselott/bibliotek", "/liselott/sok"):
        sida = owner.get(path).text
        assert 'href="/liselott/aret"' in sida, path
        assert sida.count(">Året</a>") == 1, path


def test_arets_own_nav_link_is_marked_current(areta):
    _, owner, _ = areta
    assert 'aria-current="page">Året</a>' in \
        owner.get("/liselott/aret").text


def test_the_slash_spelling_is_the_same_page(areta):
    """The ai_rek.py:531 precedent: the explicit slash rule answers the
    page itself — same endpoint, same bytes, zero redirects."""
    _, owner, _ = areta
    r = owner.get("/liselott/aret/")
    assert r.status_code == 200
    assert r.data == owner.get("/liselott/aret").data


def test_anon_get_aret_is_the_uniform_guard_posture(areta):
    """§2's public-surface proof, mirrored on the /sok posture leg: /aret is
    NOT in auth.PUBLIC_READ_PATHS/_PREFIXES, so the guard's uniform 302
    answers — byte-for-byte the refuse every private surface gives, a
    crawler included, in the bare and the prefixed and the slashed shape.
    THIS LEG IS A PIN (§7): green at base, the posture predates the route;
    named mutant = "/aret" added to auth.PUBLIC_READ_PATHS (the 302 becomes
    a 200) — .tmp-w2/mutant-aret-public.txt."""
    _, _, anon = areta
    r = anon.get("/liselott/aret")
    assert r.status_code == 302
    assert r.headers["Location"] == "/liselott/logga-in"
    sok = anon.get("/liselott/sok")
    assert r.data == sok.data                         # the SAME uniform bytes
    assert r.headers["Location"] == sok.headers["Location"]
    for path in ("/liselott/aret/", "/liselott/aret?ar=2024", "/aret"):
        r = anon.get(path)
        assert r.status_code == 302, path
        assert r.headers["Location"] == "/liselott/logga-in", path


def test_anon_bytes_cannot_move(konfigurerad):
    """THE PIN (§7): the sealed MC 12522/12551 anon bytes, IMPORTED not
    re-derived, plus the new link's absence — the nav link rides inside the
    {% if inloggad() %} header, so an anonymous page cannot carry it and
    cannot move. The plant that reddens this leg (and the legs in
    tests/test_public_filter.py): the "Året" link painted OUTSIDE the
    inloggad() block — .tmp-w2/plant-nav-outside.txt."""
    _, anon = konfigurerad
    landing = anon.get("/liselott/")
    assert _pin(landing.data) == PIN_LANDING
    assert ">Året</a>" not in landing.text
    body = anon.get("/liselott/bibliotek").data
    stripped, hits = FORM_ROW.subn(b"", body, count=1)
    assert hits == 1
    assert _pin(stripped) == PIN_SHELF
    assert ">Året</a>" not in body.decode()


def test_owner_pages_carry_the_moved_pin(konfigurerad):
    """PIN_OWNER moved IN THIS COMMIT — plan §6 W2's versioned truth: the
    inloggad-gated header gained the ONE "Året" link and with it every
    owner page byte (the truthful history rides the value's comment in
    tests/test_public_filter.py). Red at base WITH the moved value, green
    here: the owner surface moved exactly once, in this wave, for that one
    reason — and nothing else."""
    owner, _ = konfigurerad
    for path in ("/liselott/", "/liselott/bibliotek"):
        assert _pin(owner.get(path).data) == PIN_OWNER, path


# ── the empty state (the owner's first login; the feared 500 family) ────────
def test_empty_shelf_is_one_quiet_line(tmp_path, monkeypatch):
    """Fresh DB, zero rows, session just established (test_empty_owner_
    surface's shape): /aret answers 200 with ONE quiet line and NO section
    over nothing (the _hyllan law: an empty heading is a lie about data)."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    app = create_app()
    app.testing = True
    client = app.test_client()
    assert client.post("/liselott/satt-loesenord",
                       data={"loesenord": PASSWORD,
                             "bekrafta": PASSWORD}).status_code == 302
    sida = client.get("/liselott/aret")
    assert sida.status_code == 200
    assert "Inga läsår än." in sida.text
    assert "Genom åren" not in sida.text
    assert "Årets läsning" not in sida.text
    assert sida.text.count(">Året</a>") == 1           # the nav still lands
