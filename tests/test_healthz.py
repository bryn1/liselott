"""T0.1 — create_app(), /healthz and the §6.5 mount middleware (F-3 seed)."""
from flask import url_for

from app import create_app


def make_client():
    app = create_app()
    app.testing = True
    return app.test_client()


def test_healthz_ok():
    r = make_client().get("/healthz")
    assert r.status_code == 200
    assert r.data == b"ok"


def test_url_for_emits_default_prefix(monkeypatch):
    """With LISELOTT_PREFIX unset, emitted URLs are /liselott-absolute (§6.5)."""
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    app = create_app()

    @app.route("/_probe")
    def _probe():
        return url_for("healthz")

    app.testing = True
    r = app.test_client().get("/_probe")
    assert r.status_code == 200
    assert r.data == b"/liselott/healthz"


def test_url_for_uses_custom_prefix(monkeypatch):
    monkeypatch.setenv("LISELOTT_PREFIX", "/testmonly")
    app = create_app()

    @app.route("/_probe")
    def _probe():
        return url_for("healthz")

    app.testing = True
    r = app.test_client().get("/_probe")
    assert r.data == b"/testmonly/healthz"


def test_both_request_shapes_answer_identically():
    """Bare shape (nginx strips the prefix) and prefixed shape route the same."""
    app = create_app()

    @app.route("/x")
    def _x():
        return "shape"

    app.testing = True
    client = app.test_client()
    r_bare = client.get("/x")
    r_pref = client.get("/liselott/x")
    assert r_bare.status_code == r_pref.status_code == 200
    assert r_bare.data == r_pref.data == b"shape"
