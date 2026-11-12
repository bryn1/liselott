"""T2.5 — CSRF posture (§6.6, P3-2) + the P2-r4 reconciliation (DA-verdict-c3):
browser form POSTs need the session-bound token; machine routes (/seed,
/bundle, /backfill) authenticate by session cookie and rely on the same-origin
check — a MISSING Origin (curl) is allowed, a foreign one 400s. The P2-r4
exemption makes /logga-in and /satt-loesenord tokenless (same-origin check
only), so the T8.5 runbook `curl -X POST -d "loesenord=…" /logga-in` (no GET
first, no cookie, no token) works exactly as written — asserted below."""
import pytest

from app import create_app

PASSWORD = "_test_losenord_"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    app = create_app()
    app.testing = True

    @app.route("/test-form", methods=["GET", "POST"])
    def _test_form():
        return "form-ok", 200  # stands in for M4/M5 browser forms

    @app.post("/seed")
    def _seed_stub():
        return "seeded", 200  # stands in for the M6 machine route

    @app.delete("/test-form")
    def _delete_form():
        return "nope", 501  # never reached without the token

    client = app.test_client()
    r = client.post("/liselott/satt-loesenord",
                    data={"loesenord": PASSWORD, "bekrafta": PASSWORD})
    assert r.status_code == 302
    return app, client


def token(client):
    # path-scoped cookie: session_transaction needs a URL under /liselott
    with client.session_transaction("/liselott/logga-in") as sess:
        return sess["csrf"]


def test_form_post_without_token_rejected(env):
    _, client = env
    r = client.post("/liselott/test-form", data={"f": "1"})
    assert r.status_code == 400
    assert "fel-meddelande" in r.text


def test_form_post_with_wrong_token_rejected(env):
    _, client = env
    r = client.post("/liselott/test-form", data={"f": "1", "csrf": "jamalk-"})
    assert r.status_code == 400


def test_form_post_with_token_ok(env):
    _, client = env
    r = client.post("/liselott/test-form", data={"f": "1", "csrf": token(client)})
    assert r.status_code == 200


def test_form_post_foreign_origin_rejected_even_with_token(env):
    _, client = env
    r = client.post("/liselott/test-form", data={"f": "1", "csrf": token(client)},
                    headers={"Origin": "https://evil.example"})
    assert r.status_code == 400


def test_form_post_same_origin_ok(env):
    """Flask test host is localhost — a same-origin Origin passes (and in
    production https://sibbamala.com passes on the host rule: TLS ends at the
    edge, the app sees http, so the HOST is what must match)."""
    _, client = env
    r = client.post("/liselott/test-form", data={"f": "1", "csrf": token(client)},
                    headers={"Origin": "http://localhost"})
    assert r.status_code == 200


def test_machine_route_no_origin_not_rejected(env):
    """§6.6 curl posture: session-authed POST /seed (stub) WITHOUT Origin and
    without token is NOT CSRF-rejected — the runbook POSTs reach the route."""
    _, client = env
    r = client.post("/liselott/seed", data="raw body, not form data")
    assert r.status_code == 200
    assert r.data == b"seeded"


def test_machine_route_foreign_origin_rejected(env):
    _, client = env
    r = client.post("/liselott/seed", data="x", headers={"Origin": "https://evil.example"})
    assert r.status_code == 400


def test_machine_route_same_origin_ok(env):
    _, client = env
    r = client.post("/liselott/seed", data="x", headers={"Origin": "http://localhost"})
    assert r.status_code == 200


def test_curl_login_flow_works_without_token_or_origin(env):
    """P2-r4 as T8.5 writes it: tokenless, Originless form-urlencoded login —
    must reach password verification (401 wrong pw), NOT a CSRF 400."""
    _, client = env
    r = client.post("/liselott/logga-in",
                    data="loesenord=_fel_losenord_",
                    content_type="application/x-www-form-urlencoded")
    assert r.status_code == 401


def test_setup_post_works_without_token_or_origin(tmp_path, monkeypatch):
    """The T8.4 flow (browser) AND a curl-shaped first-password POST both
    stand up under the §6.6 rule: setup POST is tokenless, same-origin only."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    app = create_app()
    app.testing = True
    client = app.test_client()
    r = client.post("/liselott/satt-loesenord",
                    data="loesenord=_test_losenord_&bekrafta=_test_losenord_",
                    content_type="application/x-www-form-urlencoded")
    assert r.status_code == 302  # password set via the curl shape


def test_login_post_foreign_origin_still_400(env):
    """The exemption is TOKENLESS, not guardless: a browser POST from a
    foreign site is refused even on the exempt routes."""
    _, client = env
    r = client.post("/liselott/logga-in", data={"loesenord": PASSWORD},
                    headers={"Origin": "https://evil.example"})
    assert r.status_code == 400


def test_csrf_covers_state_changes_only(env):
    """GETs (the sweep of T2.3) never carry a token; DELETE shares the rule."""
    _, client = env
    assert client.get("/liselott/test-form").status_code == 200
    r = client.delete("/liselott/test-form")
    assert r.status_code == 400  # DELETE without token rejected
