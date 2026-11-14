"""F-3 (SEC-verdict-12497) — a trailing slash is not a login wall.

The guard matched PUBLIC_READ_PATHS by EXACT string and runs before the
router, so a shared-link spelling — sibbamala.com/liselott/bibliotek/ —
answered "Logga in" on a page the owner ruling made public ("reading is
public"). The pinned werkzeug 3.1 REMOVED the strict-slash redirect
(there is no RequestRedirect on this build — probed), so the router does
not canonicalize the spelling either: extending the guard's match alone
would trade the login wall for the router's 404, which is not "reads
public" either. The fix is therefore both halves of ONE normalization
intent: the guard tolerates the one slash on the public read (no branch
of the login wall is ever the answer for a public page), and the public
views register their slash-spelling rule beside the canonical one — an
explicit rule, not a redirect mechanism beside Flask's. Same page, 200,
zero redirects. What may NOT flip: the slash spelling of a WRITE keeps
the guard's 302, and the slash spelling of anything private keeps the
uniform wall in all three §6.1 states.
"""
import pytest

from app import create_app
from tests.test_browse import PASSWORD, seed_shelf

PUBLIC_SLASHES = ("/liselott/bibliotek/", "/liselott/bok/2/",
                  "/liselott/cover/2/")

# MC 12501: the surfaces the narrowing sent back behind the password, plus
# a private fixture id — the slash spelling meets the SAME uniform 302 as
# the bare one (guard for /sok and /rekommendationer, the views' refuse for
# the private id), never the page.
PRIVATE_SLASHES = ("/liselott/sok/", "/liselott/rekommendationer/",
                   "/liselott/bok/3/", "/liselott/cover/3/")


def _app():
    app = create_app()
    app.testing = True
    return app


@pytest.fixture()
def configured(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    (tmp_path / "covers").mkdir()
    (tmp_path / "covers/2.jpg").write_bytes(b"\xff\xd8\xff Synthetic 2")
    client = _app().test_client()
    assert client.post("/liselott/satt-loesenord",
                       data={"loesenord": PASSWORD,
                             "bekrafta": PASSWORD}).status_code == 302
    return tmp_path, client


@pytest.mark.parametrize("path", PUBLIC_SLASHES)
def test_public_pages_read_with_the_trailing_slash(configured, path):
    """200 straight through — no 302 to any wall, and real data on the
    body where the page has data."""
    _, _ = configured
    anon = _app().test_client()
    r = anon.get(path)
    assert r.status_code == 200, path
    assert "Location" not in r.headers, path
    if path == "/liselott/bibliotek/":
        assert "Stöld" in r.text
    if path == "/liselott/bok/2/":
        assert "Ann-Helén Laestadius" in r.text
    if path == "/liselott/cover/2/":
        assert r.mimetype == "image/jpeg"


def test_slash_reads_set_no_session_cookie(configured):
    _, _ = configured
    anon = _app().test_client()
    for path in PUBLIC_SLASHES + PRIVATE_SLASHES:
        assert "Set-Cookie" not in anon.get(path).headers, path


@pytest.mark.parametrize("path", PRIVATE_SLASHES)
def test_private_slash_spelling_is_the_uniform_wall(configured, path):
    """MC 12501: /sok, the rec surface and a PRIVATE id under /bok or
    /cover answer the guard's 302 in the slash spelling too — the same
    refuse the bare spelling gives, no page, no bytes."""
    _, _ = configured
    anon = _app().test_client()
    r = anon.get(path)
    assert r.status_code == 302, path
    assert r.headers["Location"] == "/liselott/logga-in", path


def test_owner_slash_spelling_still_answers_every_page(configured):
    """The slash rules were registered for the public reads (F-3) and they
    keep serving the OWNER's spelling of the now-private pages too — she
    reads everything in every spelling, unchanged."""
    _, client = configured
    for path in ("/liselott/sok/", "/liselott/rekommendationer/",
                 "/liselott/bok/3/"):
        assert client.get(path).status_code == 200, path


def test_write_on_the_slash_spelling_keeps_the_guard_refuse(configured):
    """"public to read" is not "public to write": the method rule runs
    before the slash tolerance and answers the uniform 302."""
    _, _ = configured
    anon = _app().test_client()
    r = anon.post("/liselott/bibliotek/", data={"x": "1"})
    assert r.status_code == 302
    assert r.headers["Location"] == "/liselott/logga-in"


def test_private_slash_spelling_is_still_the_wall(configured):
    _, _ = configured
    anon = _app().test_client()
    r = anon.get("/liselott/onska/")
    assert r.status_code == 302
    assert r.headers["Location"] == "/liselott/logga-in"


def test_setup_state_still_wraps_the_slash(tmp_path, monkeypatch):
    """The setup-state exception: while no password is set nothing is
    public — the slash spelling wraps to /satt-loesenord like its bare
    form."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    anon = _app().test_client()
    r = anon.get("/liselott/bibliotek/")
    assert r.status_code == 302
    assert r.headers["Location"] == "/liselott/satt-loesenord"


def test_closed_state_answers_the_slash_with_the_gate(tmp_path, monkeypatch):
    """The closed window never reaches the public branch in any spelling
    (§6.1): the pinned gate page answers, zero data."""
    import time

    import app.auth as auth
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    monkeypatch.setattr(auth, "START_TIME",
                        time.time() - auth.SETUP_WINDOW_S - 1)
    anon = _app().test_client()
    r = anon.get("/liselott/bibliotek/")
    assert "Inställningsfönstret är stängt." in r.text
