"""T4.5 — the F-3 guard: no page may emit a root-absolute URL.

F-3 (cycle 2) was the class where one hardcoded `src="/cover/1"` in a template
passes every other test in the suite and breaks the app the moment it is
mounted under a prefix. This closes it where it is actually observable — the
RENDERED page — over every src/href/action attribute, for the 302 Locations,
for both request shapes, and for a different mount prefix.

Two things about the mechanism, both measured here rather than assumed:

* The session cookie carries `Path=<prefix>` (§6.3), so only the PREFIXED
  request shape is authenticated in a browser — the bare shape is what nginx
  forwards after stripping the prefix, and nginx forwards the Cookie header
  with it. The both-shapes leg therefore passes the session cookie explicitly;
  that is the production shape, not a test trick.
* The plan's parenthetical suggested 501 stubs for pages that have not landed.
  A 501 stub is plain text with no attributes, so those legs would pass by
  checking nothing; /lagg-till, /onska and /rekommendationer are swept as what
  they answer today — the app's own 404 page, which does carry the nav. When
  those pages land this file checks their real markup without being edited.
"""
import re

import pytest

from app import create_app
from tests.test_browse import PASSWORD, seed_shelf  # one synthetic corpus

# NOT_YET_LANDED reflects reality as pages land (M5): /lagg-till landed with
# T5.3, so it is swept as the REAL page now — the SWEEP check needs no edit;
# only this constant moves. /onska moves with T5.4, /rekommendationer with M6.
NOT_YET_LANDED = ("/onska", "/rekommendationer")
SWEEP = ("/", "/bibliotek", "/bok/1", "/bok/2", "/bok/9999", "/sok?q=a",
         "/logga-in", "/redigera/1",
         "/satt-loesenord", "/robots.txt") + NOT_YET_LANDED
# everything else must 302 an anonymous visitor; the allow-listed four may not
ANON_PROTECTED = ("/bibliotek", "/bok/1", "/sok?q=a", "/logga-ut", "/cover/1",
                  "/byter-losenord", "/redigera/1") + NOT_YET_LANDED
_ATTR_RE = re.compile(r'\b(src|href|action)\s*=\s*"([^"]*)"', re.I)
_OK_NON_URL = ("#", "mailto:")


@pytest.fixture()
def tmp_data(tmp_path, monkeypatch):
    """An EMPTY state dir: legs that want rows call tests.test_browse.seed_shelf
    on it before the app opens it."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    return tmp_path


@pytest.fixture()
def app_at():
    def build(prefix=None):
        if prefix is None:
            import os
            os.environ.pop("LISELOTT_PREFIX", None)
        else:
            import os
            os.environ["LISELOTT_PREFIX"] = prefix
        app = create_app()
        app.testing = True
        return app
    return build


@pytest.fixture()
def authed(tmp_data, app_at):
    # the shelf must have CARDS: a sweep over an empty page proves nothing
    seed_shelf(tmp_data / "liselott.db")
    app = app_at(None)
    client = app.test_client()
    r = client.post("/liselott/satt-loesenord", data={
        "loesenord": PASSWORD, "bekrafta": PASSWORD})
    assert r.status_code == 302
    # name=value straight off the response: the cookie is Secure (§6.3), so a
    # test client over http will not hand it back via get_cookie(), and its
    # Path is the prefix — Path is BROWSER-side metadata, which is exactly why
    # the bare shape needs the header carried by hand, as nginx does.
    return app, client, r.headers["Set-Cookie"].split("=", 1)[1].split(";")[0]


def attrs(html):
    return _ATTR_RE.findall(html or "")


def assert_prefixed(client, path, prefix="/liselott"):
    """One page: every emitted URL starts with the mount prefix. A bare
    in-page anchor or a mailto is the only value allowed not to. Returns how
    many URLs were checked so the caller can prove the sweep was not vacuous."""
    seen = 0
    for name, value in attrs(client.get(path).get_data(as_text=True)):
        if value.startswith(_OK_NON_URL):
            continue
        assert value.startswith(prefix + "/"), (path, name, value)
        seen += 1
    return seen


# ── the sweep ───────────────────────────────────────────────────────────────
def test_every_emitted_url_on_every_page_is_prefix_absolute(authed):
    app, client, session_value = authed
    checked = 0
    for path in SWEEP:
        r = client.get("/liselott" + path)
        assert r.status_code in (200, 404), (path, r.status_code)
        checked += assert_prefixed(client, "/liselott" + path)
    # anti-vacuity: the shelf carries 5 cards x (cover src + page href) plus
    # the nav and the stylesheet. Measured this run: 30+ URLs.
    assert checked >= 25, f"only {checked} URLs swept"


def test_the_not_yet_landed_pages_swept_as_the_real_404_page(authed):
    """They answer the app's own 404 page, which carries the nav — so the
    prefix claim is checked over them today, not skipped."""
    _, client, _ = authed
    for path in NOT_YET_LANDED:
        r = client.get("/liselott" + path)
        assert (r.status_code, "Sidan hittas inte" in r.text) == (404, True), path
        assert 'href="/liselott/bibliotek"' in r.text, path


def test_redirect_locations_are_prefix_absolute(authed):
    """The other half of F-3: a Location without the prefix lands the owner
    outside the mount entirely."""
    _, client, _ = authed
    r = client.get("/liselott/logga-ut")
    assert r.status_code == 302
    assert r.headers["Location"].startswith("/liselott/"), r.headers["Location"]
    anon = create_app().test_client()          # same state, no session
    for path in ANON_PROTECTED:
        r = anon.get(path)                     # bare shape: the guard still 302s
        assert r.status_code == 302, path
        assert r.headers["Location"].startswith("/liselott/"), (
            path, r.headers["Location"])


def test_both_request_shapes_return_identical_prefixed_markup(authed):
    """THE F-3 regression class in one assertion. nginx delivers the BARE
    shape; the browser sends the prefixed one. Same page, same bytes, prefix
    on every URL — either way. The session cookie is passed explicitly because
    its Path is the prefix and a browser would only attach it to the prefixed
    URL; nginx forwards the header with the stripped path (see module
    docstring)."""
    app, client, session_value = authed
    bare_client = app.test_client()
    # the session cookie in the jar at Path=/ — the value nginx hands over with
    # the stripped path. (A hand-written Cookie header cannot work: werkzeug's
    # jar REWRITES HTTP_COOKIE from its own store, VERIFIED this session.)
    bare_client.set_cookie("liselott_session", session_value, path="/")
    for path in ("/", "/bibliotek", "/sok?q=a", "/bok/1", "/bok/9999"):
        prefixed = client.get("/liselott" + path)
        bare = bare_client.get(path)
        assert bare.status_code == prefixed.status_code, path
        assert bare.status_code in (200, 404), (path, bare.status_code)
        assert bare.data == prefixed.data, path
        assert 'href="/liselott/bibliotek"' in prefixed.get_data(
            as_text=True), path


def test_a_custom_prefix_moves_every_url(tmp_data, app_at):
    seed_shelf(tmp_data / "liselott.db")
    """Same tree, different mount: a literal `/liselott` baked into a template
    surfaces here, and so does a literal that forgot the prefix altogether."""
    app = app_at("/testmonly")
    client = app.test_client()
    assert client.post("/testmonly/satt-loesenord", data={
        "loesenord": PASSWORD, "bekrafta": PASSWORD}).status_code == 302
    checked = 0
    for path in ("/testmonly", "/testmonly/bibliotek", "/testmonly/sok?q=a",
                 "/testmonly/bok/1", "/testmonly/bok/2"):
        n = assert_prefixed(client, path, prefix="/testmonly")
        assert n >= 5, (path, n)
        checked += n
    assert checked >= 25, checked
    page = client.get("/testmonly/bibliotek").get_data(as_text=True)
    assert "/liselott/" not in page            # the default is not baked in
