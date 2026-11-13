"""T2.3 — guard sweep over the §6.4 exhaustive allow-list in ALL THREE §6.1
states (P2-7 + P2-c): configured → every non-allow-listed route 302 /logga-in;
unconfigured+open → 302 /satt-loesenord; unconfigured+closed → gate page
everywhere EXCEPT /healthz, which answers 200 `ok` in every state (three
separate healthz assertions below). Stub routes answer 501 until the real
routes land (M4+); reaching a stub would mean the guard leaked."""
import pytest

from app import create_app

PASSWORD = "_test_losenord_"

# §6.4: every one of these must be behind the guard. Paths without a rule yet
# get registered as 501 stubs — the guard fires before any view.
PROTECTED = (
    "/bibliotek", "/bok/1", "/sok?q=x", "/lagg-till", "/onska",
    "/rekommendationer", "/cover/1", "/rapa/omslag", "/rapa/omslag-rapport",
    "/rekommendation-rapport", "/seed", "/bundle", "/backfill",
    "/byter-losenord", "/backup",
)


def unimplemented(app):
    """The PROTECTED paths with no GET-bearing rule of their own — i.e. where
    T2.3's 501 stub is still the thing a GET reaches. M4 adaptation: as
    milestones land real GET routes (`/bibliotek`, `/sok` …), `make_app` must
    NOT shadow them with a stub — Werkzeug resolves an identical rule by
    registration order, and a test stub registered after create_app would
    otherwise answer instead of the page under test. The guard claims are
    unchanged either way: a stubbed path still has to answer 501 to the owner,
    an implemented path has to answer with the real page, and neither may ever
    see a guard redirect or the gate page. (The stub endpoints are excluded so
    this stays correct after the stubs are registered; a POST-only path like
    /byter-losenord has no GET rule, so its stub stays in place.)"""
    get_paths = {rule.rule for rule in app.url_map.iter_rules()
                 if "GET" in rule.methods and not rule.endpoint.startswith("stub")}
    return {e.split("?")[0] for e in PROTECTED if e.split("?")[0] not in get_paths}


def make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    app = create_app()
    app.testing = True
    for path in sorted(unimplemented(app)):
        def _stub(_path=path):
            return _path, 501

        app.add_url_rule(path, endpoint=f"stub{path}", view_func=_stub)
    return app


def configured_client(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    client = app.test_client()
    r = client.post("/liselott/satt-loesenord",
                    data={"loesenord": PASSWORD, "bekrafta": PASSWORD})
    assert r.status_code == 302
    return app, client


def test_configured_state_sweep(tmp_path, monkeypatch):
    """§6.4 allow-list sweep with the password set: data routes all 302 to
    the login page; /healthz and /robots.txt answer; a stub is NEVER reached."""
    _, client = configured_client(tmp_path, monkeypatch)
    for entry in PROTECTED:
        r = client.get(entry)
        assert r.status_code == 302, entry
        assert r.headers["Location"] == "/liselott/logga-in", entry
        assert b"stub" not in r.data, entry  # the 501 view never ran
    assert client.get("/healthz").status_code == 200
    assert client.get("/healthz").data == b"ok"  # healthz assertion 1/3
    r = client.get("/static/nonexistent.css")
    assert r.status_code == 404  # static is allow-listed (not redirected)
    r = client.post("/seed", data="x")
    assert r.status_code == 302  # machine routes too (§6.4)


def test_logged_in_client_reaches_the_stubs(tmp_path, monkeypatch):
    """Guard is not a wall: with the owner session the SAME paths reach the
    views (501 stubs where a route has not landed yet, the real page where it
    has — T4.2 landed /bibliotek). What may NEVER happen is the guard answering
    an owner-authenticated request with a redirect or the gate page."""
    app = make_app(tmp_path, monkeypatch)
    still_stubbed = unimplemented(app)
    client = app.test_client()
    client.post("/liselott/satt-loesenord",
                data={"loesenord": PASSWORD, "bekrafta": PASSWORD})
    for entry in PROTECTED:
        path = entry.split("?")[0]
        # Prefixed shape: the browser's real request URL (nginx strips the
        # prefix in production, but the cookie travels with the FULL URL).
        r = client.get("/liselott" + entry)
        if path in still_stubbed:
            assert (r.status_code, r.data) == (501, path.encode()), entry
        else:
            assert r.status_code == 200, entry
            assert "Inställningsfönstret är stängt." not in r.text, entry


def test_unconfigured_open_state_sweep(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    client = app.test_client()
    for entry in PROTECTED:
        r = client.get(entry)
        assert r.status_code == 302, entry
        assert r.headers["Location"] == "/liselott/satt-loesenord", entry
    assert client.get("/healthz").data == b"ok"  # healthz assertion 2/3


def test_closed_window_gate_except_healthz(tmp_path, monkeypatch):
    import time

    import app.auth as auth
    app = make_app(tmp_path, monkeypatch)
    monkeypatch.setattr(auth, "START_TIME", time.time() - auth.SETUP_WINDOW_S - 1)
    client = app.test_client()
    for entry in PROTECTED:
        r = client.get(entry)
        assert "Inställningsfönstret är stängt." in r.text, entry
        assert b"stub" not in r.data, entry
    r = client.get("/healthz")
    assert r.status_code == 200 and r.data == b"ok"  # healthz assertion 3/3
