"""MC 12551 — the PUBLIC shelf's filters (owner 2026-11-15, verbatim): "The
public page needs filter by score, year, search by author, title and year".

The contract (card /tmp/briefs/L-pubfilter.md): `GET /bibliotek` accepts
`betyg=1..5`, `ar=YYYY` and `q=<title OR author>`, combinable with AND,
INVALID VALUES IGNORED (calm page, never a 500) — and every narrowing runs on
the PUBLIC SET rows the ONE public filter already returned
(`books.load_books(public_only=True)` under `books.PUBLIC_SET_SQL`, MC 12501).
`app/filtrering.py` owns the rules; this file owns the proof, and the heart of
the proof is the LEAK side: an anonymous reader who filters or searches must
never meet an unrated book, whatever she types in.

THE BYTE PINS (the MC 12522 idiom, MEASURED on the pre-change tree
`6d4d576` before one line was edited, over the fixture below): the no-param
anonymous pages render as they always did. The stylesheet URL carries
`?v=<APP_VERSION>` and APP_VERSION IS the commit sha (T4.4), so a raw hash of
any page changes on every unrelated commit — the token is normalized to a
fixed literal and EVERYTHING ELSE is pinned byte for byte. At `6d4d576` the
raw served sizes were 2911 B (landing), 2621 B (shelf), 4313 B (each owner
page); normalized (token → `?v=PIN`): the numbers below.

The fixture is the synthetic shelf (tests/test_browse, corpus-free) plus TWO
private rows this file owns: unrated `read` rows — "Tyst i Tived" in a year NO
public book populated (the year-list leak) and "Ångest i Ön" sharing the public
year 2025 (the year-filter leak). Swedish diacritics on purpose: the fold must
be åäö-safe on both sides of every match.

MC 12745 — the row enters the LANDING (owner 2026-11-21, verbatim: "The public
page needs a filter and search function" + the phone answer "The page im
watching on my phone has no filters"). MC 12551 fixed the page we looked at
(/bibliotek, an orphan no link points to), not the page the owner opens (`/`).
The landing's BEHAVIOUR legs live in tests/test_landing_filter.py (file
hygiene: this one was at the ceiling; the split moves no rule, only proof);
the moved PIN rides HERE, beside the family it belongs to — it moves
legitimately (the form entered the page), re-measured in the commit that
moved it, with the row's full footprint pinned away beside it
(PIN_LANDING_ROW_FREE) so the page's gain is EXACTLY one filter row.
"""
import hashlib
import re
import sqlite3
from urllib.parse import quote

import pytest

from app import create_app
from tests.test_browse import PASSWORD, seed_shelf

PRIVATE_ROWS = [
    (6, "Tyst i Tived", 2019, 2023, "2023-05-04", None, "bok", "read",
     "Anna Anonym"),
    (7, "Ångest i Ön", 2020, 2025, "2025-02-11", None, "bok", "read",
     "Sören Åkesson"),
]
PRIVATE_TITLES = tuple(row[1] for row in PRIVATE_ROWS)
PRIVATE_AUTHORS = tuple(row[8] for row in PRIVATE_ROWS)
PRIVATE_IDS = tuple(row[0] for row in PRIVATE_ROWS)
PRIVATE_ONLY_YEAR = 2023                   # no PUBLIC book was read this year


PUBLIC_IDS = (1, 2, 4, 5)                  # seed_shelf: rated 5/4/3 + wishlist
PUBLIC_TITLES = ("Goda natten Agda", "Nattfjärden", "Floden minns")
WISHLIST_TITLE = "En skatt av silver"
PUBLIC_YEARS = [2026, 2025, 2024]          # the shelf's public read years

# MEASURED on 6d4d576 with THIS fixture (normalized ?v= token, see docstring).
# RE-MEASURED IN THE MC 12745 COMMIT — the ONLY reason the landing bytes moved:
# the public filter row entered the page (owner 2026-11-21, verbatim: "The
# public page needs a filter and search function" + "The page im watching on
# my phone has no filters"; MC 12551 had fixed /bibliotek, the page we looked
# at, not the landing the owner opens). The value it replaces —
# (2874, 5678075...) — stood from 6d4d576 through bd2a257 and is NOT retired:
# it lives on as PIN_LANDING_ROW_FREE below, the strip proof that the page
# gained EXACTLY the one form row. PIN_SHELF/PIN_OWNER are UNTOUCHED.
PIN_LANDING_ROW_FREE = (2874, "56780752833e96a9a15573580428ea62d8e05b6ad6ba8b9e4dc424ad25d089af")
PIN_LANDING = (3686, "52751cf2e285b60dd59fedf5232c106c962890fe90f76c4b5821dc77c9d28762")
PIN_SHELF = (2584, "fb5269d1a052c7d98b7c481273fcd54330d06e2be534a238f9d5cf51554f084a")
# RE-MEASURED IN THE MC 12734 (M12 W2) COMMIT — the ONLY reason the owner
# bytes moved: the inloggad-gated header gained the ONE "Året" nav link
# (PLAN-M12 REV 2 §6 W2 row; page + link law in tests/test_aret.py). The
# previous value (4276, fedfe610...) stood from 6d4d576 through 48abe41; the
# two anon pins directly above are UNTOUCHED (header renders for the logged
# in only — the W2 anon zero-diff proof). Owner landing == owner shelf bytes
# (MC 12522) still holds at the new value.
PIN_OWNER = (4324, "12b0bfe45157467272f97b3188a30535335daff57c749b6d07e73e822caeee4a")

FORM_ROW = re.compile(b'\n<form class="hyll-filtrering".*?</form>', re.DOTALL)


def _norm(body: bytes) -> bytes:
    """The one version-dependent byte run in these pages, pinned away: the
    cache key on the stylesheet URL (APP_VERSION = the commit, T4.4)."""
    return re.sub(rb'\?v=[^"]*', b'?v=PIN', body)


def _pin(body: bytes):
    norm = _norm(body)
    return len(norm), hashlib.sha256(norm).hexdigest()


def _ids(html: str):
    return {int(m) for m in re.findall(r'href="/liselott/bok/(\d+)"', html)}


def _shelf(html: str) -> str:
    """The SHELF render only — everything after the filter row. Two reasons a
    name may appear on a filtered page and still mean NOTHING leaked: the
    form's year <option> list legitimately names every public year, and the
    q box echoes what the reader herself typed (escaped). Absence is therefore
    asserted over the cards, where a private book would actually stand."""
    return html.split("</form>")[-1]


def _app():
    app = create_app()
    app.testing = True
    return app


def _insert_rows(conn, rows):
    """Rows through the real schema — the shape MC 12551 seeded inline; an
    author is attached only when the row names one (the MC 12733 shape rows
    carry none). One insert, both fixtures below."""
    now = "2026-11-15T00:00:00Z"
    for (bid, title, year, read_year, date_read, rating, fmt, status,
         author) in rows:
        conn.execute(
            "INSERT INTO book (id, title, year, read_year, date_read, rating,"
            " format, status, book_key, created, updated)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (bid, title, year, read_year, date_read, rating, fmt, status,
             f"key-{bid}", now, now))
        if author:
            conn.execute("INSERT INTO author (name) VALUES (?)", (author,))
            conn.execute(
                "INSERT INTO book_author (book_id, author_id) VALUES (?, "
                "(SELECT id FROM author WHERE name = ?))", (bid, author))
    conn.commit()


def _seed(tmp_path, extra=()):
    conn_seed = sqlite3.connect(tmp_path / "liselott.db")
    conn_seed.close()
    seed_shelf(tmp_path / "liselott.db")
    conn = sqlite3.connect(tmp_path / "liselott.db")
    _insert_rows(conn, tuple(PRIVATE_ROWS) + tuple(extra))
    conn.close()


def _configure_and_clients():
    owner = _app().test_client()
    assert owner.post("/liselott/satt-loesenord",
                      data={"loesenord": PASSWORD,
                            "bekrafta": PASSWORD}).status_code == 302
    return owner, _app().test_client()


def _wrap_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)


@pytest.fixture()
def konfigurerad(tmp_path, monkeypatch):
    """The synthetic shelf + the two private rows + the password set, and the
    two clients the contract speaks about: the anonymous visitor and the
    logged-in owner."""
    _wrap_env(tmp_path, monkeypatch)
    # (MC 12606: this fixture also deleted PRIS_DOOR_TOKEN, a name the retired
    # price door read; nothing reads it now, so the pin is gone. The byte pins
    # below are UNTOUCHED — measured at 6d4d576 and green here.)
    _seed(tmp_path)
    return _configure_and_clients()


# ── the byte pins: the no-param public pages did not move ───────────────────
def test_default_anonymous_landing_is_the_pinned_page_plus_one_form_row(konfigurerad):
    """MC 12745 moved this pin ONCE, legitimately: the filter row entered the
    landing. Everything the row does not touch is still the 6d4d576 page —
    strip the row's FULL footprint (its own leading newline, the same
    include-line shape the shelf leg above proves) and the pinned bytes come
    back byte for byte. A second row sneaking in would leave residue: hits."""
    _, anon = konfigurerad
    r = anon.get("/liselott/")
    assert r.status_code == 200
    body = r.data
    assert _pin(body) == PIN_LANDING
    stripped, hits = FORM_ROW.subn(b'', body, count=1)
    assert hits == 1, "the landing must carry exactly one filter row"
    assert _pin(stripped) == PIN_LANDING_ROW_FREE, \
        "the landing changed beside the form row"
    assert _ids(body.decode()) == set(PUBLIC_IDS)    # the anchors, unchanged


def test_default_anonymous_shelf_is_the_pinned_page_plus_one_form_row(konfigurerad):
    """The shelf page gains EXACTLY the filter row and nothing else: remove
    that one <form> and what is left is the pre-change page byte for byte (the
    MC 12522 byte-identity idiom, measured at 6d4d576)."""
    _, anon = konfigurerad
    body = anon.get("/liselott/bibliotek").data
    stripped, hits = FORM_ROW.subn(b'', body, count=1)
    assert hits == 1, "the page must carry exactly one filter row"
    assert _pin(stripped) == PIN_SHELF, "the shelf render changed beside the form"
    assert len(body) > len(stripped)
    assert _ids(FORM_ROW.sub(b'', body, count=1).decode()) == set(PUBLIC_IDS)


def test_owner_pages_carry_no_form_and_her_params_are_inert(konfigurerad):
    """The filter is the PUBLIC reader's: the owner's landing and shelf are the
    pinned bytes (and each other's bytes, MC 12522), and `?betyg=` on HER shelf
    changes NOTHING — her view changed NOTHING when the scope narrowed."""
    # MC 12745: the landing branch is the owner's too — no form and inert
    # params THERE, exactly as on the shelf (the zero-byte law, MC 12551).
    owner, _ = konfigurerad
    for path in ("/liselott/", "/liselott/bibliotek"):
        assert _pin(owner.get(path).data) == PIN_OWNER, path
        assert b"hyll-filtrering" not in owner.get(path).data, path
        assert owner.get(path + "?betyg=4&ar=2025&q=tyst").data == \
            owner.get(path).data, path
    plain = owner.get("/liselott/bibliotek").data
    assert "Tyst i Tived" in plain.decode()        # her unfiltered shelf, still


# ── the params, one at a time and combined ──────────────────────────────────
def test_betyg_shows_only_books_with_that_rating(konfigurerad):
    _, anon = konfigurerad
    for betyg, title, away in ((5, "Goda natten Agda", "Nattfjärden"),
                              (4, "Nattfjärden", "Floden minns"),
                              (3, "Floden minns", "Goda natten Agda")):
        html = anon.get(f"/liselott/bibliotek?betyg={betyg}").text
        assert title in html, betyg
        assert away not in html, betyg
        assert _ids(html) <= set(PUBLIC_IDS)


def test_ar_shows_only_the_books_read_that_year(konfigurerad):
    """`ar` is the shelf's OWN year — the read_year the section heading shows.
    The private row 7 was read in 2025 too, and it stays out: the year filter
    narrows the public set, it never widens it."""
    _, anon = konfigurerad
    html = anon.get("/liselott/bibliotek?ar=2025").text
    shelf = _shelf(html)
    assert "Nattfjärden" in shelf
    assert "Goda natten Agda" not in shelf
    assert "Ångest i Ön" not in shelf and "Sören Åkesson" not in shelf
    assert ">2025<" in shelf and ">2026<" not in shelf


def test_q_matches_title_and_author_case_and_diacritic_safely(konfigurerad):
    """§7's fold on BOTH sides: lowercase matches the seeded title, the
    un-accented spelling matches the accented one, and an author's surname is
    a hit. The owner's words: "search by author, title and year"."""
    _, anon = konfigurerad
    for q, title in (("Nattfjärden", "Nattfjärden"),
                     ("nattfjärden", "Nattfjärden"),
                     ("nattfjarden", "Nattfjärden"),     # å folded on both sides
                     ("hemmar", "Goda natten Agda"),     # author, not title
                     ("HEMMAR", "Goda natten Agda"),
                     ("silver", WISHLIST_TITLE)):
        shelf = _shelf(anon.get(f"/liselott/bibliotek?q={q}").text)
        assert title in shelf, q
        assert _ids(shelf) <= set(PUBLIC_IDS), q


def test_q_is_title_and_author_only_never_a_genre(konfigurerad):
    """The card names the two fields; §7's genre key is the OWNER's /sok, and
    it is not smuggled onto the public page: a genre word is just text here."""
    _, anon = konfigurerad
    html = anon.get("/liselott/bibliotek?q=kriminalitet").text   # seed genre of 2
    assert "Inga träffar" in html and "bok-kort" not in _shelf(html)


def test_the_params_combine_with_and(konfigurerad):
    """AND is the rule: book 2 alone is rated 4 AND read in 2025 AND named
    Nattfjärden; drop any one condition and the answer is a different page."""
    _, anon = konfigurerad
    shelf = _shelf(anon.get(
        "/liselott/bibliotek?betyg=4&ar=2025&q=nattfjärden").text)
    assert "Nattfjärden" in shelf and "Goda natten Agda" not in shelf
    # betyg=4 AND ar=2026 is the empty read-set (book 2 was read in 2025):
    assert "Nattfjärden" not in _shelf(
        anon.get("/liselott/bibliotek?betyg=4&ar=2026").text)
    # and betyg=5 AND ar=2024 leaves no read row at all — only the wishlist,
    # which no betyg/ar param speaks for (the leg below pins that rule).
    assert _ids(_shelf(anon.get(
        "/liselott/bibliotek?betyg=5&ar=2024").text)) == {5}


def test_filtered_out_shelf_is_one_calm_line_and_no_chrome(konfigurerad):
    _, anon = konfigurerad
    html = anon.get("/liselott/bibliotek?q=inget-sådant-namn-finns").text
    assert "Inga träffar" in html
    assert 'class="bok-kort"' not in html and 'class="grupp"' not in html
    assert "Hyllan är tom" not in html             # the owner's empty-diary copy
    assert "Din hylla" in html                     # the page's own h1 stays
    assert html.count("<h2") == 0                  # no heading over nothing


def test_wishlist_is_narrowed_by_q_only(konfigurerad):
    """The contract's line: the wishlist section filters by q ONLY — it carries
    neither a rating nor a read year, so no betyg/ar param speaks for it (and
    no such param can leak it either: the ruling made it public as it is)."""
    _, anon = konfigurerad
    for query in ("betyg=5", "ar=2026", "q=silver", "betyg=3&ar=2024"):
        assert WISHLIST_TITLE in _shelf(
            anon.get(f"/liselott/bibliotek?{query}").text), query
    assert WISHLIST_TITLE not in _shelf(
        anon.get("/liselott/bibliotek?q=nattfjärden").text)


def test_the_year_select_offers_the_public_years_only(konfigurerad):
    """THE YEAR-LIST LEAK: an <option value="2023"> would publish a year only a
    PRIVATE row populated. The list is read off the SAME public rows the shelf
    renders, and it stays the full list under a filter (a select that shrinks
    to the filtered year traps the reader)."""
    _, anon = konfigurerad
    for path in ("/liselott/bibliotek", "/liselott/bibliotek?betyg=5",
                 "/liselott/bibliotek?ar=2026&q=natt"):
        options = re.findall(r'<option value="(\d{4})"',
                             anon.get(path).text)
        assert options == [str(y) for y in PUBLIC_YEARS], path
        assert f'>{PRIVATE_ONLY_YEAR}<' not in anon.get(path).text, path


# ── the leak legs: no param combination reaches the private half ────────────
def test_no_private_name_surfaces_under_any_single_param(konfigurerad):
    """Every private title and author — as typed, folded, uppercased, and with
    one letter off — answers a page WITHOUT it, while a public title proves the
    page painted (a non-vacuity per leg, never a green on an empty body)."""
    _, anon = konfigurerad
    needles = []
    for word in PRIVATE_TITLES + PRIVATE_AUTHORS:
        needles += [word, word.lower(), word.upper(), word.split()[0],
                    word.replace("ö", "o").replace("Ä", "A").replace("å", "a")]
    for needle in needles:
        shelf = _shelf(anon.get(
            f"/liselott/bibliotek?q={quote(needle)}").text)
        for word in PRIVATE_TITLES + PRIVATE_AUTHORS:
            assert word not in shelf, (needle, word)
    assert PUBLIC_TITLES[1] in _shelf(
        anon.get("/liselott/bibliotek?q=nattfj").text)


def test_betyg_times_year_fuzz_never_renders_a_private_card(konfigurerad):
    """The param-fuzz loop the card asks for: every betyg x every year present
    x a few q's. Every card that renders is a public-set card, by id and by
    name; the anti-vacuity counter proves the loop really painted cards."""
    _, anon = konfigurerad
    painted = 0
    for betyg in (None, 1, 2, 3, 4, 5):
        for year in PUBLIC_YEARS + [PRIVATE_ONLY_YEAR, 1900]:
            for q in ("", "natt", "ö", "%"):
                query = "&".join(
                    f"{name}={quote(str(value))}" for name, value in
                    (("betyg", betyg), ("ar", year), ("q", q))
                    if value is not None and value != "")
                r = anon.get(f"/liselott/bibliotek?{query}")
                assert r.status_code == 200, query
                shelf = _shelf(r.text)
                assert _ids(shelf) <= set(PUBLIC_IDS), query
                for word in PRIVATE_TITLES + PRIVATE_AUTHORS:
                    assert word not in shelf, (query, word)
                for pid in PRIVATE_IDS:
                    assert f'href="/liselott/bok/{pid}"' not in shelf, (query, pid)
                painted += len(_ids(shelf))
    assert painted >= 20, painted           # the loop rendered real public cards


def test_like_wildcards_and_quotes_are_literal_text(konfigurerad):
    """The public q is a substring test over rows already in hand — there is no
    SQL LIKE to escape, so the metacharacters of BOTH matching dialects this
    app could ever have spoken are ordinary characters: SQL's "%" and "_" and
    the word ESCAPE, the glob's "*" and "?" and bracket class, quotes and a
    classic `OR 1=1`. Pinned semantics: "_" is not one character, "*" does not
    match everything (which is the needle that WOULD surface the private half
    if this door ever learned wildcards), while the plain title still matches.
    """
    _, anon = konfigurerad
    for q in ("%", "_", "%%", "%Nattfjärden", "Nattfjärden%", "Nattfjärd_",
              "Nattfjärden'", '\\"', "' OR 1=1 --", "ESCAPE", "%_%",
              "Tyst i Tived%", "%Tyst%", "_yst i Tived", "\\%\\_",
              "*", "**", "*Tyst*", "Nattfjärden*", "Nattfjärd?n", "?yst",
              "[Tt]yst i Tived", "[!a]*"):
        r = anon.get(f"/liselott/bibliotek?q={quote(q)}")
        assert r.status_code == 200, q                 # literal text, never an error
        # NO stored title or author carries any of these characters, so a
        # LITERAL match answers the empty state. A needle that paints cards is
        # the door speaking a wildcard dialect — the leak shape, red by design.
        assert "Inga träffar" in r.text, q
        shelf = _shelf(r.text)
        assert "bok-kort" not in shelf, q
        assert "Tyst i Tived" not in shelf and "Ångest i Ön" not in shelf, q
        assert _ids(shelf) <= set(PUBLIC_IDS), q
    # the wildcard semantics, pinned BOTH ways: "_" is not one character…
    assert "Inga träffar" in anon.get(
        "/liselott/bibliotek?q=" + quote("Nattfjärd_")).text
    # …and the plain title is still found.
    assert "Nattfjärden" in _shelf(
        anon.get("/liselott/bibliotek?q=" + quote("Nattfjärden")).text)
    # the q box echoes what was typed ESCAPED — markup is text, never markup:
    r = anon.get("/liselott/bibliotek?q=" + quote('<svg onload=alert(1)>'))
    assert "<svg onload=alert(1)>" not in r.text
    assert 'value="&lt;svg onload=alert(1)&gt;"' in r.text


def test_invalid_params_are_ignored_and_the_page_stays_calm(konfigurerad):
    """betyg=6, a year with a letter, an unknown name: a BAD value is the
    ABSENT value — 200, the calm public shelf, nothing private, no traceback
    and no 500 (§9's posture: a filter typo is not an error page)."""
    _, anon = konfigurerad
    ignorerade = ("betyg=6", "betyg=0", "betyg=99", "betyg=abc", "betyg=-3",
                  "betyg=4.0", "betyg=5x", "betyg=5 5", "ar=199", "ar=20261",
                  "ar=20a6", "ar=-2026", "ar=2026.0", "slump=1",
                  "betyg=6&ar=99", "betyg=9&ar=abc&hej=1")
    for param in ignorerade:
        r = anon.get(f"/liselott/bibliotek?{param}")
        assert r.status_code == 200, param
        assert "Traceback" not in r.text, param
        shelf = _shelf(r.text)
        assert "Goda natten Agda" in shelf and "Nattfjärden" in shelf, param
        for word in PRIVATE_TITLES + PRIVATE_AUTHORS:
            assert word not in shelf, (param, word)
    # The sharpest combination: broken betyg/ar AND a q that IS the private
    # title — the bad params drop out, the good one filters honestly (the
    # wishlist is narrowed by q too), and the private title appears NOWHERE on
    # the page but escaped inside the reader's own search box.
    r = anon.get("/liselott/bibliotek?betyg=abc&ar=199&q=" + quote("tyst"))
    assert r.status_code == 200
    assert "Inga träffar" in r.text and "bok-kort" not in _shelf(r.text)
    assert r.text.count("Tyst i Tived") == 0
    r = anon.get("/liselott/bibliotek?q=" + quote("Tyst i Tived"))
    assert r.text.count("Tyst i Tived") == 1        # only the echo, never a card


def test_a_huge_or_padded_query_stays_calm_and_leaks_nothing(konfigurerad):
    """A 4 KB q is VALID text that matches nothing: the calm "Inga träffar"
    page, never an error. A whitespace-padded betyg is the honest value after
    the strip. Both pinned, both leak-free."""
    _, anon = konfigurerad
    r = anon.get("/liselott/bibliotek?q=" + "x" * 4096)
    assert r.status_code == 200 and "Traceback" not in r.text
    assert "Inga träffar" in r.text and "bok-kort" not in _shelf(r.text)
    r = anon.get("/liselott/bibliotek?betyg=%205%20")
    assert r.status_code == 200
    shelf = _shelf(r.text)
    assert "Goda natten Agda" in shelf and "Nattfjärden" not in shelf
    for word in PRIVATE_TITLES + PRIVATE_AUTHORS:
        assert word not in shelf, word


# ── the neighbours: the guard, the owner's /sok, the write sweep ────────────
def test_the_sweeps_still_hold_with_params_on(konfigurerad):
    """Params are not a new door: HEAD stays a read (200), every write aimed at
    a public path keeps the guard's uniform 302, and /sok — public-set search
    was NEVER one of them — keeps refusing anonymous reads with params on."""
    _, anon = konfigurerad
    r = anon.head("/liselott/bibliotek?betyg=4&ar=2025&q=natt")
    assert r.status_code == 200 and not r.data
    for path, refuse in (("/bibliotek?betyg=4", 302), ("/bok/2?ar=2025", 302),
                         ("/sok?q=natt", 302), ("/onska/lagg-till?q=natt", 302),
                         ("/betyg/2?q=natt", 302), ("/backup?kind=db", 302)):
        r = anon.post(path, data={"betyg": "5"})
        assert r.status_code == refuse, path
        if refuse == 302:
            assert r.headers["Location"] == "/liselott/logga-in", path
        assert not (200 <= r.status_code < 300), path


def test_the_private_sok_is_untouched_by_the_public_filters(konfigurerad):
    """§7's five keys stay the OWNER's mechanism, byte-for-byte the legs
    tests/test_search_e2e.py already pin: her /sok still finds the private half
    and still answers the genre key the public page refuses."""
    owner, anon = konfigurerad
    html = owner.get("/liselott/sok?q=Tyst i Tived").text
    assert "Tyst i Tived" in html and "Sök" in html
    # the genre key is hers alone and still works (book 2 carries the seed genre)
    assert "Nattfjärden" in owner.get("/liselott/sok?q=kriminalitet").text
    assert anon.get("/liselott/sok?q=hemmar").status_code == 302
    assert owner.get("/liselott/bibliotek?q=hemmar").status_code == 200

