"""T2.3 — guard sweep over the §6.4 exhaustive allow-list in ALL THREE §6.1
states (P2-7 + P2-c): configured → every non-allow-listed route 302 /logga-in;
unconfigured+open → 302 /satt-loesenord; unconfigured+closed → gate page
everywhere EXCEPT /healthz, which answers 200 `ok` in every state (three
separate healthz assertions below) and /static/, which answers as an asset in
every state (M8-hotfix-3, MC 12451: the closed gate page served under a .css
URL is what Cloudflare cached for 4 h). The ROOT is the one public page in the
first two states and the pinned gate page in the third (M8 staging gate,
MC 12451): each state test below asserts GET / -> 200, never a 302. The
mirror-DROPPED root names (QUARANTINED below) answer the guard's own 404 to
anonymous in every state that 302s (M8-hotfix-2, MC 12451). Stub
routes answer 501 until the real routes land (M4+); reaching a stub would
mean the guard leaked."""
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

# M8-hotfix-2 (MC 12451): mirror-DROPPED root names the lane staging gate
# (vm106-staging-gate.sh §6) probes — a quarantined name passes only on
# 404/403, never on the guard's uniform 302 (which fingerprints the auth
# gate and reads as reachable). import_overrides.csv is the personal-data
# leg of P0-1: one owner row, never served anonymous.
QUARANTINED = (
    "/DESIGN.md", "/LEDGER.md", "/README.md", "/hosting.yaml",
    "/data-import/import_overrides.csv", "/server.py",
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
    this stays correct after the stubs are registered; a path with a real GET
    rule — /byter-losenord since P1-1, MC 12451 — is swept as the real page,
    never stubbed.)"""
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
    # the root leg (MC 12451): the landing answers 200, never a redirect,
    # carries the ONE legal door and none of the owner's shelf or nav.
    r = client.get("/")
    assert r.status_code == 200, "root must not 302 (§6.4 landing leg)"
    assert 'href="/liselott/logga-in"' in r.text
    assert "Välj ditt lösenord" not in r.text
    assert "Din hylla" not in r.text


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
            # get_data + a lenient decode, not .text: T9.2's /backup answers
            # with a sqlite file, and a binary owner download must not be able
            # to break the sweep that checks the GATE never answered it.
            body = r.get_data().decode("utf-8", "replace")
            assert "Inställningsfönstret är stängt." not in body, entry


def test_unconfigured_open_state_sweep(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    client = app.test_client()
    for entry in PROTECTED:
        r = client.get(entry)
        assert r.status_code == 302, entry
        assert r.headers["Location"] == "/liselott/satt-loesenord", entry
    assert client.get("/healthz").data == b"ok"  # healthz assertion 2/3
    # the root leg (MC 12451): in the open state the landing's ONE door is
    # the setup flow — never the login door, never a 302 of its own.
    r = client.get("/")
    assert r.status_code == 200, "root must not 302 (§6.4 landing leg)"
    assert 'href="/liselott/satt-loesenord"' in r.text
    assert "Välj ditt lösenord" in r.text
    assert "Logga in" not in r.text


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
    # the root leg (MC 12451): in the closed state the §6.1-pinned gate
    # page answers the root too — 200, zero app data, no landing doors.
    r = client.get("/")
    assert r.status_code == 200, "root must not 302 (§6.4 landing leg)"
    assert "Inställningsfönstret är stängt." in r.text
    assert "Välj ditt lösenord" not in r.text
    r = client.get("/healthz")
    assert r.status_code == 200 and r.data == b"ok"  # healthz assertion 3/3


def test_closed_window_serves_static_assets_not_the_gate(tmp_path, monkeypatch):
    """M8-hotfix-3 (MC 12451), the live bug: in the closed state the guard
    answered GET /liselott/static/css/app.css with the GATE PAGE — 200, but
    text/html — and Cloudflare caches .css-extension responses for 4 h by
    default, so it froze the gate HTML under the stylesheet URL and the
    landing rendered unstyled until the TTL expired. Static is
    zero-personal-data by construction (css/js/fonts/placeholder svg) — the
    same §6.4 argument the allow-list already makes in the two open states —
    so the closed branch passes /static/ through too. Everything else keeps
    the §6.1-pinned gate page. The gate page's OWN <link> stylesheet is the
    leg that actually renders a styled page, so it is fetched from the href
    the page emits (prefix + ?v= and all), exactly as a browser does."""
    import re
    import time

    import app.auth as auth
    app = make_app(tmp_path, monkeypatch)
    monkeypatch.setattr(auth, "START_TIME", time.time() - auth.SETUP_WINDOW_S - 1)
    client = app.test_client()
    gate = client.get("/liselott/")
    assert gate.status_code == 200
    assert "Inställningsfönstret är stängt." in gate.text
    for entry in ("/", "/bibliotek", "/logga-in", "/x"):
        r = client.get(entry)
        assert "Inställningsfönstret är stängt." in r.text, entry
    href = re.search(r'href="([^"]*?/static/[^"]*)"', gate.text).group(1)
    assert href.startswith("/liselott/static/css/app.css?v="), href
    css = client.get(href)
    assert css.status_code == 200, "the gate page's own stylesheet must load"
    assert css.mimetype == "text/css", "an asset URL answers as an asset"
    assert "Inställningsfönstret" not in css.get_data(as_text=True)


def test_quarantined_file_shapes_404_configured_state(tmp_path, monkeypatch):
    """M8-hotfix-2 (MC 12451), the state the lane ran in when the gate went
    RED: anonymous GETs of every mirror-DROPPED root name 404 (plain 404.html,
    no Location header — the uniform 302 would read as "reachable" to the
    staging probe). Both request shapes answer alike (§6.5 middleware strips
    the prefix before the guard). Static stays allow-listed 200, and the
    extension-less unknown keeps its T2.6 302 to /logga-in — that contract
    is NOT churned."""
    _, client = configured_client(tmp_path, monkeypatch)
    for path in QUARANTINED:
        r = client.get(path)
        assert r.status_code == 404, path
        assert "Location" not in r.headers, path
        assert "hittas inte" in r.text.lower(), path
        r = client.get("/liselott" + path)  # prefixed shape, same answer
        assert r.status_code == 404, path
    assert client.get("/static/css/app.css").status_code == 200
    r = client.get("/något-okänt")
    assert r.status_code == 302
    assert r.headers["Location"] == "/liselott/logga-in"


def test_quarantined_file_shapes_404_open_state(tmp_path, monkeypatch):
    """The 404 posture holds pre-setup too (unconfigured+window-open): the
    lane probe must never read a quarantined name, in no state that 302s."""
    app = make_app(tmp_path, monkeypatch)
    client = app.test_client()
    for path in QUARANTINED:
        assert client.get(path).status_code == 404, path
    r = client.get("/något-okänt")
    assert (r.status_code, r.headers["Location"]) == (
        302, "/liselott/satt-loesenord")


def test_logged_in_file_shape_still_reaches_flask_404(tmp_path, monkeypatch):
    """The owner's answer to an unknown file-shaped path is unchanged: the
    guard passes it through and Flask's own 404 answers — the anonymous 404
    is byte-for-byte the same page, so the posture cannot fingerprint the
    session either way."""
    app = make_app(tmp_path, monkeypatch)
    client = app.test_client()
    client.post("/liselott/satt-loesenord",
                data={"loesenord": PASSWORD, "bekrafta": PASSWORD})
    for path in QUARANTINED:
        r = client.get(path)
        assert r.status_code == 404, path
        assert "hittas inte" in r.text.lower(), path


def test_closed_window_quarantined_names_and_robots_404(tmp_path, monkeypatch):
    """F-E + F-F (TEST-verdict 2026-11-13, MC 12451): in the CLOSED state the
    gate page answered the quarantined names AND /robots.txt with 200 — the
    staging posture says those names answer 404/403 ONLY, and a 200 reads
    "reachable" to a probe. The 404 is now STATE-INVARIANT: _file_shaped (the
    §6.4 allow-list's /robots.txt is file-shaped by that rule too, and is
    named a second time beside it) runs BEFORE the gate page renders. What
    the closed state must KEEP answering — the landing gate page, /static,
    and the setup door's 403 — is asserted here too, so the fix cannot trade
    one pinned behaviour for the other."""
    import time

    import app.auth as auth
    app = make_app(tmp_path, monkeypatch)
    monkeypatch.setattr(auth, "START_TIME",
                        time.time() - auth.SETUP_WINDOW_S - 1)
    client = app.test_client()
    for path in QUARANTINED:
        r = client.get(path)
        assert r.status_code == 404, path
        assert "Location" not in r.headers, path
        assert "Inställningsfönstret" not in r.text, path
        r = client.get("/liselott" + path)         # prefixed shape, same 404
        assert r.status_code == 404, path
    r = client.get("/robots.txt")                   # F-F, explicitly named
    assert r.status_code == 404
    assert "Disallow" not in r.text and "Inställningsfönstret" not in r.text
    # the pinned closed-state answers stay untouched (§6.1):
    gate = client.get("/")
    assert gate.status_code == 200
    assert "Inställningsfönstret är stängt." in gate.text
    assert client.get("/static/css/app.css").status_code == 200
    assert client.get("/static/css/app.css").mimetype == "text/css"
    r = client.get("/något-utan-punkt")             # shapeless: the gate page
    assert "Inställningsfönstret är stängt." in r.text
    r = client.post("/satt-loesenord",
                    data={"loesenord": PASSWORD, "bekrafta": PASSWORD})
    assert r.status_code == 403
