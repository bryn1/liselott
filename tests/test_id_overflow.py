"""F-2 (SEC-verdict-12497) — an id beyond sqlite's INTEGER domain never
reaches the bind, so it can never Overflow into a 500.

werkzeug's int converter matches \\d+ without bound; binding an id >= 2**63
into sqlite OverflowErrors ("Python int too large to convert to SQLite
INTEGER") with no handler — the anonymous traceback generator the verdict
measured live on the freshly-public /bok and /cover (a 23-digit GET, one
crawler walk, log flood). sqlite INTEGER is signed 64-bit: outside its
domain no row CAN stand, so the range check runs BEFORE the bind in every
posture and the traceback stays dead. The ANSWER is posture-split by
MC 12501 (owner ruling 2026-11-14: "The rest behind password"): the
anonymous reader meets the same uniform login refuse every id outside the
public set gets — an unbindable id must not answer differently than a
private one, or the no-answer shape itself fingerprints the id space; the
owner, who reads everything, keeps the route's own 404 page.
2**63-1 itself stays the normal path.
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
def test_overflow_id_never_reaches_the_bind(configured, route, i):
    """app.testing re-raises: on the pre-fix tree this leg is the verdict's
    OverflowError straight through — no silent 500 to paper over it. MC
    12501 posture: the anonymous answer is the uniform login refuse — the
    SAME status and Location a private id and a nonexistent in-range id
    give, so no answer shape fingerprints the id space."""
    anon = create_app().test_client()   # same state, no session: the edge
    r = anon.get(route + i)
    assert r.status_code == 302, (route, i, r.status_code)
    assert r.headers["Location"] == "/liselott/logga-in", (route, i)
    assert "Internal Server Error" not in r.text   # the bind never ran


def test_boundary_in_range_stays_the_normal_path(configured):
    """The bound is drawn exactly at sqlite's: 2**63-1 binds and honestly
    meets no exception — anonymous the uniform refuse, owner the plain
    no-row 404, never the traceback."""
    anon = create_app().test_client()
    for path in ("/liselott/bok/" + BOUNDARY_IN, "/liselott/cover/" + BOUNDARY_IN):
        r = anon.get(path)
        assert r.status_code == 302, path
        assert "Internal Server Error" not in r.text
        assert configured.get(path).status_code == 404, path


def test_overflow_404_is_the_owner_answer(configured):
    """The owner reads everything, so for her an unbindable id is simply
    the route's own not-found page — the §9 404, zero echo (MC 12501:
    the anonymous uniform refuse above is the reader-facing half)."""
    r = configured.get("/liselott/bok/" + "9" * 23)
    assert r.status_code == 404
    assert "hittas inte" in r.text.lower()
    assert "Set-Cookie" not in r.headers
