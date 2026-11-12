"""T0.1 — create_app(), /healthz and the §6.5 mount middleware (F-3 seed).

M2 adaptation (§6.1/§6.4): from T2.1 on every non-allow-listed route is behind
the auth guard, so the mount-probe legs below establish a session through the
first-run setup route first — the URL-emission assertions are unchanged.
SESSION_COOKIE_PATH "/" here emulates the production fact that the browser
attaches the /liselott cookie to the full prefixed URL before nginx strips the
prefix, so the BARE shape reaches the app with the cookie header too (the
test-client jar only emulates that with a root path; the T2.2 cookie-contract
test asserts the real Path=/liselott)."""
from flask import url_for

from app import create_app

PROBE_PASSWORD = "_probe_losenord_"


def make_client():
    app = create_app()
    app.testing = True
    return app.test_client()


def authed_client(tmp_path, monkeypatch):
    """App + client on a fresh state dir; routes must be registered before
    login() — Flask forbids add_url_rule after the first request. Settings
    live in the DB, so a shared state dir would make the second first-run
    setup 404; each probe test gets its own."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    app = create_app()
    app.config["SESSION_COOKIE_PATH"] = "/"
    app.testing = True
    return app, app.test_client()


def login(client, prefix="/liselott"):
    """First-run setup establishes the owner session (also proven by T2.1)."""
    r = client.post(f"{prefix}/satt-loesenord", data={
        "loesenord": PROBE_PASSWORD, "bekrafta": PROBE_PASSWORD})
    assert r.status_code == 302


def test_healthz_ok():
    r = make_client().get("/healthz")
    assert r.status_code == 200
    assert r.data == b"ok"


def test_url_for_emits_default_prefix(tmp_path, monkeypatch):
    """With LISELOTT_PREFIX unset, emitted URLs are /liselott-absolute (§6.5)."""
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    app, client = authed_client(tmp_path, monkeypatch)

    @app.route("/_probe")
    def _probe():
        return url_for("healthz")

    login(client)
    r = client.get("/_probe")
    assert r.status_code == 200
    assert r.data == b"/liselott/healthz"


def test_url_for_uses_custom_prefix(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_PREFIX", "/testmonly")
    app, client = authed_client(tmp_path, monkeypatch)

    @app.route("/_probe")
    def _probe():
        return url_for("healthz")

    login(client, prefix="/testmonly")
    r = client.get("/_probe")
    assert r.data == b"/testmonly/healthz"


def test_both_request_shapes_answer_identically(tmp_path, monkeypatch):
    """Bare shape (nginx strips the prefix) and prefixed shape route the same."""
    app, client = authed_client(tmp_path, monkeypatch)

    @app.route("/x")
    def _x():
        return "shape"

    login(client)
    r_bare = client.get("/x")
    r_pref = client.get("/liselott/x")
    assert r_bare.status_code == r_pref.status_code == 200
    assert r_bare.data == r_pref.data == b"shape"
