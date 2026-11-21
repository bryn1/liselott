"""MC 12745 — the filter row enters the LANDING (owner 2026-11-21, verbatim:
"The public page needs a filter and search function" + the phone answer "The
page im watching on my phone has no filters").

The history this leg set completes: MC 12551 (2026-11-15, same owner ask)
added the row to /bibliotek — an orphan page no link points to — while the
landing, the ONE page visitors and the owner actually open (MC 12522 made it
the public shelf), stayed formless. Same owner, second report, ONE root:
the fix went to the page we looked at, not the page he opens. The cure is
reuse again (the MC 12522 idiom): the landing's view hands over the SAME
`filtrering`/`ar_all` its rows were already narrowed with, start.html
includes the SAME _publik-filtrering.html, and the partial learned ONE word
— `filtreringsmal`, the endpoint the form posts to — so a filter chosen on
the landing stays on the landing. No second query path, no copied markup,
no rule beside filtrering.py's.

The legs: the landing renders the row (fields, button) with its form aimed
at `/`; the landing's year <option> list is the public list ONLY (the
year-list leak follows any entrance); a param narrows the landing EXACTLY as
it narrows /bibliotek — same rows by id, same calm "Inga träffar" state,
zero private bytes on either; an invalid param is the absent param; the
wishlist exemption (q only, never betyg/ar) behaves; the WRAPPED setup state
and the OWNER branch carry no form (dead control / zero-byte law); and
MC 12733's public status law — unrated reading/aborted invisible, the rated
aborted row a plain public card facing the params — survives the new
entrance.

RED-FIRST: written against `bd2a257` before routes.py/start.html/the
partial moved — 5 failed (the landing pin, the form row, the year list, the
parity, the calm invalid-param leg); transcript red-first.txt in the wave's
audit dir. The legs green AT BASE (the landing already RAN the narrow on its
rows — only the form was missing) are named PINS in their docstrings, each
with its mutant. PLANTS (§7 law, all four in .tmp-ld/ beside this file's
transcripts, each restore byte-verified): owner-branch leak → RED on exactly
the two owner legs; setup-branch leak → RED on exactly the setup leg;
action-jump → RED on the three landing-action legs; params-discard → RED on
the five narrowing legs. The byte pins that had to STAND (PIN_SHELF,
PIN_OWNER, PIN_ANON_BOK) ride tests/test_public_filter.py and
tests/test_edit_path.py, green here by the full suite.
"""
import re

import pytest

from tests.test_browse import seed_shelf
from tests.test_public_filter import (FORM_ROW, PUBLIC_YEARS,
                                      PRIVATE_AUTHORS, PRIVATE_ONLY_YEAR,
                                      PRIVATE_TITLES, WISHLIST_TITLE, _app,
                                      _configure_and_clients, _ids, _seed,
                                      _shelf, _wrap_env, konfigurerad)

# MC 12733's widened domain, the test_status_model shape (year 0, no date,
# no author) — ids kept clear of test_public_filter's PRIVATE_ROWS 6/7
# because THIS file's fixture seeds both halves. 8/9 are unrated (private);
# 10 is the RATED aborted card.
NY_RADER = [
    (8, "Springlådan", None, 0, None, None, "bok", "reading", None),
    (9, "Brottslingen", None, 0, None, None, "bok", "aborted", None),
    (10, "Fjordbreven", None, 0, None, 3, "bok", "aborted", None),
]


@pytest.fixture()
def inlagd(tmp_path, monkeypatch):
    """No password yet, window open: the state with NO public anything
    (test_public_landing's `inslagning` — kept small HERE because the leg
    below speaks about the FILTER, not about the entrance)."""
    _wrap_env(tmp_path, monkeypatch)
    seed_shelf(tmp_path / "liselott.db")
    return _app().test_client()


@pytest.fixture()
def breddad(tmp_path, monkeypatch):
    """The `konfigurerad` shelf PLUS the three new-status rows MC 12733
    admits — the M12 law's own shapes riding the landing's fixture."""
    _wrap_env(tmp_path, monkeypatch)
    _seed(tmp_path, NY_RADER)
    return _configure_and_clients()


# ── the entrance: the SAME row, aimed at THIS page ──────────────────────────
def test_landing_carries_one_form_row_that_stays_on_the_landing(konfigurerad):
    """The row is the partial's, rendered on both pages; the ACTION is the
    page's own (the partial's variable, default /bibliotek): a filter from
    `/` answers `/` — no surprise jump to a page the reader never opened.
    /bibliotek keeps posting to itself: the default did not move."""
    _, anon = konfigurerad
    forms = FORM_ROW.findall(anon.get("/liselott/").data)
    assert len(forms) == 1, "the landing must carry exactly one filter row"
    for field in (b'action="/liselott/"', b'name="betyg"', b'name="ar"',
                  b'name="q"', b'<button type="submit">Filtrera</button>'):
        assert field in forms[0], field
    assert 'action="/liselott/bibliotek"' in anon.get(
        "/liselott/bibliotek").text


def test_the_landing_year_select_offers_the_public_years_only(konfigurerad):
    """The year-list leak follows the entrance: the landing's <option> list
    is read off the SAME public rows, stays the full list under a filter, and
    never names the private-only year."""
    _, anon = konfigurerad
    for path in ("/liselott/", "/liselott/?betyg=5", "/liselott/?ar=2026&q=natt"):
        options = re.findall(r'<option value="(\d{4})"', anon.get(path).text)
        assert options == [str(y) for y in PUBLIC_YEARS], path
        assert f'>{PRIVATE_ONLY_YEAR}<' not in anon.get(path).text, path


# ── parity: the SAME rows the /bibliotek legs already pin ───────────────────
PARQUER = ("", "betyg=5", "betyg=4", "ar=2025", "ar=2023", "q=nattfjärden",
           "q=silver", "q=kriminalitet", "betyg=4&ar=2025&q=nattfjärden",
           "betyg=5&ar=2024", "betyg=4&ar=2026", "q=inget-sådant-namn-finns")


def test_landing_narrows_exactly_as_bibliotek(konfigurerad):
    """The card's parity law, and the reason NO second rule was written: the
    landing runs the SAME _hylldata read and the SAME narrow() as /bibliotek,
    so every param answers the SAME rows by id on both entrances, the calm
    "Inga träffar" line appears on both or neither, and the private half
    surfaces on NEITHER."""
    _, anon = konfigurerad
    for query in PARQUER:
        lr, sr = anon.get(f"/liselott/?{query}"), anon.get(
            f"/liselott/bibliotek?{query}")
        assert lr.status_code == sr.status_code == 200, query
        landing = _shelf(lr.text)
        assert _ids(landing) == _ids(_shelf(sr.text)), query
        assert ("Inga träffar" in lr.text) == \
            ("Inga träffar" in sr.text), query
        for word in PRIVATE_TITLES + PRIVATE_AUTHORS:
            assert word not in landing, (query, word)


def test_invalid_params_on_the_landing_stay_the_absent_value(konfigurerad):
    """§9's calm posture travels with the row: a bad value is the absent one
    on the landing too — 200, the row still standing, the full public shelf,
    nothing private, no traceback."""
    _, anon = konfigurerad
    for param in ("betyg=6", "ar=20a6", "slump=1", "betyg=9&ar=abc&hej=1"):
        r = anon.get(f"/liselott/?{param}")
        assert r.status_code == 200 and "Traceback" not in r.text, param
        assert 'action="/liselott/"' in r.text, param   # the row still stands
        shelf = _shelf(r.text)
        assert "Goda natten Agda" in shelf and "Nattfjärden" in shelf, param
        for word in PRIVATE_TITLES + PRIVATE_AUTHORS:
            assert word not in shelf, (param, word)


def test_the_wishlist_exemption_behaves_on_the_landing(konfigurerad):
    """q narrows the wish rows, betyg/ar never speak for them — the SAME
    narrow() rows the /bibliotek leg pins, now through the landing's door.
    GREEN at base (the landing already RAN the narrow on its rows; only the
    form was missing) — a pin, not a red-first leg; its named plant is the
    params-discard (`_hylldata(None)` on the landing branch): the wish rows
    then survive a q that must remove them (.tmp-ld/plant-params-discard.txt)."""
    _, anon = konfigurerad
    for query in ("betyg=5", "ar=2026", "q=silver", "betyg=3&ar=2024"):
        assert WISHLIST_TITLE in _shelf(
            anon.get(f"/liselott/?{query}").text), query
    assert WISHLIST_TITLE not in _shelf(
        anon.get("/liselott/?q=nattfjärden").text)


# ── the branches that must stay form-free ───────────────────────────────────
def test_the_setup_state_landing_has_no_form(inlagd):
    """A wrapped site has no public shelf — and no dead control either: the
    setup branch hands the template NO `filtrering`, so the partial renders
    NOTHING. Its `{%- if filtrering %}` closes over its own whitespace, so
    this page is not merely form-free but byte-for-byte the setup landing
    that stood before the row existed (the setup-branch plant,
    .tmp-ld/plant-setup-branch.txt, reddens this leg AND lands a form on a
    page with nothing to filter)."""
    r = inlagd.get("/liselott/")
    assert r.status_code == 200
    assert b"hyll-filtrering" not in r.data
    assert 'href="/liselott/satt-loesenord">Välj ditt lösenord</a>' in r.text
    assert 'class="bok-lank"' not in r.text
    for param in ("", "betyg=5"):
        assert b"hyll-filtrering" not in inlagd.get(
            f"/liselott/?{param}").data, param


def test_the_m12_status_law_survives_the_new_entrance(breddad):
    """MC 12733's public posture on BOTH entrances: the unrated
    reading/aborted rows are invisible and their status words unpainted, the
    RATED aborted row is a plain public card — and on the landing it faces
    the params exactly as it does on /bibliotek (rating narrows, the 0-
    sentinel year means every ?ar= lawfully excludes it). GREEN at base for
    the same reason as the wish leg — pin, plant named: params-discard
    (.tmp-ld/plant-params-discard.txt), and the leak half rides the public-set
    mutant already named in tests/test_status_model.py."""
    _, anon = breddad
    for path in ("/liselott/", "/liselott/bibliotek"):
        body = anon.get(path).text
        shelf = _shelf(body)
        assert _ids(shelf) == {1, 2, 4, 5, 10}, path
        for borta in ("Springlådan", "Brottslingen"):
            assert borta not in shelf, (path, borta)
        assert "Fjordbreven" in shelf, path          # rated ⇒ public, plain
        assert "Läser nu" not in body and "Avbruten" not in body, path

    def landing(query):
        return _shelf(anon.get(f"/liselott/?{query}").text)

    assert "Fjordbreven" in landing("betyg=3")
    assert "Fjordbreven" not in landing("betyg=4")
    for ar in (2024, 2025, 2026):
        assert "Fjordbreven" not in landing(f"ar={ar}"), ar
    assert "Fjordbreven" in landing("q=fjordbreven")
    assert "Fjordbreven" not in landing("q=silver")
    for borta in ("Springlådan", "Brottslingen"):
        assert borta not in landing(f"q={borta.lower()}"), borta
