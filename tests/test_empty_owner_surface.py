"""M8-hotfix-4 (MC 12451) — the owner surface on the EMPTY state: fresh
SQLite, zero books, password just set, session established — the exact state
the owner lands in on first login ("choosing and refreshing").

The live 500 turned out to be the vm106 mirror's cache-bust rewriting the
Jinja import strings of the SERVED templates (journal:
jinja2.exceptions.TemplateNotFound: _bokkort.html?v=865e19bd; lane fix
cc9f14a = hosting.yaml mirror.cachebust=off), NOT app logic — the local
prod-shape repro of this state renders every page 200 with zero tracebacks.
These legs pin the contract the feared 500 family would have violated, and
they hold the import-resolution seam shut on purpose: a `{% from %}` import
executes when the template renders, before (and even without) a single card,
which is exactly why production 500ed on the empty shelf — an empty page is
still a page that must RESOLVE its partials, so a broken partial name is
red here, on any corpus size.
"""
import pytest

from app import create_app
from tests.test_browse import PASSWORD


@pytest.fixture()
def fresh_owner(tmp_path, monkeypatch):
    """Clean app on an isolated state dir + the first-login POST that sets
    the password and lands the session logged-in (test_setup's shape, zero
    seeded rows — THAT is the state under test)."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    app = create_app()
    app.testing = True
    client = app.test_client()
    r = client.post("/liselott/satt-loesenord",
                    data={"loesenord": PASSWORD, "bekrafta": PASSWORD})
    assert r.status_code == 302           # she lands logged-in (§6.1)
    return app, client


def test_first_login_lands_on_the_empty_shelf(fresh_owner):
    _, client = fresh_owner
    r = client.get("/liselott/")
    assert r.status_code == 200           # §6.1: 200, not 302
    assert "<h1>Din hylla</h1>" in r.text
    assert "Hyllan är tom" in r.text      # the honest empty copy


# (path, the empty-state copy that proves the page RENDERED) — the pages that
# import a partial (_bokkort.html: shelf, search, wishlist) are in here
# deliberately, see the module docstring.
EMPTY_PAGES = [
    ("/liselott/bibliotek", "Hyllan är tom"),
    ("/liselott/sok?q=x", "Inga träffar"),           # asked, corpus empty
    ("/liselott/onska", "Inga önskningar"),
    ("/liselott/rekommendationer", "Betygsätt några"),
    ("/liselott/rapa/omslag", "Alla böcker har omslag."),
]


@pytest.mark.parametrize("path,copy", EMPTY_PAGES)
def test_owner_page_200_with_its_empty_copy(fresh_owner, path, copy):
    _, client = fresh_owner
    r = client.get(path)
    assert r.status_code == 200
    assert copy in r.text


def test_sok_blank_is_the_hint_not_the_no_hits_page(fresh_owner):
    """An empty q is a blank page (traffar is None), NOT a zero-result page —
    different sentences, both on the empty corpus."""
    _, client = fresh_owner
    for url in ("/liselott/sok", "/liselott/sok?q=", "/liselott/sok?q=%20"):
        r = client.get(url)
        assert r.status_code == 200
        assert "Sök på titel" in r.text
        assert "Inga träffar" not in r.text


def test_lagg_till_form_renders_on_empty_state(fresh_owner):
    _, client = fresh_owner
    r = client.get("/liselott/lagg-till")
    assert r.status_code == 200
    assert 'name="titel"' in r.text


def test_rapport_doors_answer_zero(fresh_owner):
    _, client = fresh_owner
    assert client.get("/liselott/rapa/omslag-rapport").json == {
        "total": 0, "with_cover": 0, "missing": 0, "manual": 0,
        "unobtainable": []}
    assert client.get("/liselott/rapa/rekommendation-rapport").json == {
        "rated": 0, "candidates": 0, "pool_nonempty": False}


def test_login_then_refresh_answers_the_shelf(fresh_owner):
    """The owner's literal flow: password set earlier, a fresh browser
    session logs in through /logga-in and REFRESHES — the shelf answers, and
    answers again (the M6 session fix and the 500 both died at "refresh")."""
    app, _ = fresh_owner
    client = app.test_client()
    r = client.post("/liselott/logga-in", data={"loesenord": PASSWORD})
    assert r.status_code == 302
    assert r.headers["Location"] == "/liselott/"
    for path in ("/liselott/", "/liselott/bibliotek"):
        for _ in range(2):                # "and refreshing"
            assert client.get(path).status_code == 200
