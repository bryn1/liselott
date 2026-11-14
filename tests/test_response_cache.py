"""F-5 (SEC-verdict-12497) — personalized HTML says no-store beside its
Vary: Cookie.

Every response of this app carries Vary: Cookie (the guard reads the
session on every request), but the owner-painted HTML carried NO
Cache-Control — the verdict's P4: a downstream cache that treats Vary
casually sits on her diary page. The pin, HTML-scoped and posture-split:
an owner-session text/html response carries Cache-Control: no-store;
anonymous public HTML (the MC 12497 contract) is NOT pinned — the app
forbids nothing it does not need to, and Cloudflare does not cache HTML
by default; the static immutable pin (T4.4 / M8-hotfix-3) is asserted
untouched in BOTH postures, because /static/ is zero-personal-data by
construction and an owner browsing never makes an asset personal.
"""
import pytest

from app import create_app

PASSWORD = "_test_losenord_"
STATIC_PIN = "public, max-age=31536000, immutable"


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
    return client                        # the logged-in owner client


def test_owner_html_carries_no_store_beside_vary(configured):
    for path in ("/liselott/bibliotek", "/liselott/byter-losenord",
                 "/liselott/sok"):
        r = configured.get(path)
        assert r.status_code == 200, path
        assert r.headers.get("Cache-Control") == "no-store", path
        assert "cookie" in r.headers.get("Vary", "").lower(), path


def test_owner_login_redirect_carries_no_store(configured):
    """The login POST's Set-Cookie rides a 302 with an HTML body — that
    response is personalized too and must not sit in any downstream cache."""
    fresh = create_app().test_client()
    r = fresh.post("/liselott/logga-in", data={"loesenord": PASSWORD})
    assert r.status_code == 302
    assert r.headers.get("Cache-Control") == "no-store"


def test_anonymous_public_html_is_not_pinned(configured):
    assert configured.get("/liselott/bibliotek").status_code == 200
    anon = create_app().test_client()
    for path in ("/liselott/", "/liselott/bibliotek", "/liselott/sok"):
        r = anon.get(path)
        assert r.status_code == 200, path
        assert "Cache-Control" not in r.headers, path


def test_static_pin_holds_in_both_postures(configured):
    """The immutable asset pin is the one Cache-Control this fix may not
    disturb — neither an owner session nor the public flip reaches it."""
    r = configured.get("/liselott/static/css/app.css")
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == STATIC_PIN
    anon = create_app().test_client()
    r = anon.get("/liselott/static/css/app.css")
    assert r.headers["Cache-Control"] == STATIC_PIN
