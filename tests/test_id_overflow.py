"""F-2 (SEC-verdict-12497) — an id beyond sqlite's INTEGER domain answers
the route's own 404, never a 500.

werkzeug's int converter matches \\d+ without bound; binding an id >= 2**63
into sqlite OverflowErrors ("Python int too large to convert to SQLite
INTEGER") with no handler — the anonymous traceback generator the verdict
measured live on the freshly-public /bok and /cover (a 23-digit GET, one
crawler walk, log flood). sqlite INTEGER is signed 64-bit: outside its
domain no row CAN stand, so the honest answer is the route's own 404 page
before the bind ever happens — byte-shape identical to the in-range no-row
404, anonymous and owner indistinguishable, zero echo, no traceback.
2**63-1 itself stays the normal path: no row, plain 404.
"""
import pytest

from app import create_app

PASSWORD = "_test_losenord_"

# outside sqlite's signed 64-bit domain (>= 2**63): unbindable by definition
OVERFLOW = ("9" * 23, "9" * 300, str(2 ** 63), str(2 ** 64))
BOUNDARY_IN = str(2 ** 63 - 1)   # the largest id sqlite can still bind


@pytest.fixture()
def configured(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    app = create_app()
    app.testing = True
    client = app.test_client()
    assert client.post("/liselott/satt-loesenord",
                       data={"loesenord": PASSWORD,
                             "bekrafta": PASSWORD}).status_code == 302
    return client                       # the OWNER client (session rides)


@pytest.mark.parametrize("route", ("/liselott/bok/", "/liselott/cover/"))
@pytest.mark.parametrize("i", OVERFLOW)
def test_overflow_id_answers_the_routes_own_404(configured, route, i):
    """app.testing re-raises: on the pre-fix tree this leg is the verdict's
    OverflowError straight through — no silent 500 to paper over it."""
    anon = create_app().test_client()   # same state, no session: the edge
    r = anon.get(route + i)
    assert r.status_code == 404, (route, i, r.status_code)
    assert "Internal Server Error" not in r.text
    assert "hittas inte" in r.text.lower()   # the §9 404 page: the route's
    assert "Location" not in r.headers       # own not-found shape


def test_boundary_in_range_stays_the_normal_path(configured):
    """The bound is drawn exactly at sqlite's: 2**63-1 binds and honestly
    reports "no such row" — the same 404, never the same exception."""
    anon = create_app().test_client()
    for path in ("/liselott/bok/" + BOUNDARY_IN, "/liselott/cover/" + BOUNDARY_IN):
        r = anon.get(path)
        assert r.status_code == 404, path
        assert "Internal Server Error" not in r.text


def test_overflow_404_is_owner_indistinguishable(configured):
    """The owner's answer to the same id is the same page — the fix may
    not fingerprint the session, and the guard never reaches its redirect
    branch for these paths (the /bok/ /cover/ prefixes are public-read)."""
    r = configured.get("/liselott/bok/" + "9" * 23)
    assert r.status_code == 404
    assert "hittas inte" in r.text.lower()
    assert "Set-Cookie" not in r.headers
