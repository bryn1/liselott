"""T2.1 — first-run setup window (§6.1, F-5: no land-grab — the window is
bounded 20 min from start and only open while unconfigured). Negative legs:
valid POST after the window -> 403 + hash STILL unset; every route then serves
the closed-window page with zero app data; /healthz stays 200 `ok` in EVERY
state (P2-c three-state matrix)."""
import sqlite3
import time

import pytest

import app.auth as auth
from app import create_app

PASSWORD = "_test_losenord_"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Fresh app on an isolated state dir, production-shaped env (no dev flag,
    default prefix). Stub routes answer 501 — reaching one proves the guard
    let the request through; a 302/403/gate proves it did not."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    flask_app = create_app()
    flask_app.testing = True

    @flask_app.route("/")
    def _root_stub():
        return "rot", 200  # real page arrives M4; here it proves the session

    @flask_app.route("/bibliotek")
    def _bibliotek_stub():
        return "stub", 501

    return flask_app, flask_app.test_client(), tmp_path


def setting(tmp_path, key):
    conn = sqlite3.connect(tmp_path / "liselott.db")
    try:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    except sqlite3.OperationalError:  # no settings table yet = nothing set
        return None
    finally:
        conn.close()
    return row[0] if row else None


def test_unconfigured_open_redirects_everything_to_setup(env):
    _, client, _ = env
    r = client.get("/bibliotek")
    assert r.status_code == 302
    assert r.headers["Location"] == "/liselott/satt-loesenord"


def test_setup_page_copy_and_selector(env):
    _, client, _ = env
    r = client.get("/satt-loesenord")
    assert r.status_code == 200
    assert "Fönstret för att sätta lösenord är öppet i 20 min från start" in r.text
    assert 'id="loesenord"' in r.text


def test_short_or_mismatch_password_rejected(env):
    _, client, _ = env
    r = client.post("/satt-loesenord",
                    data={"loesenord": "kort", "bekrafta": "kort"})
    assert r.status_code == 400
    assert "fel-meddelande" in r.text
    r = client.post("/satt-loesenord",
                    data={"loesenord": PASSWORD, "bekrafta": "annat-lösenord"})
    assert r.status_code == 400
    assert "fel-meddelande" in r.text


def test_valid_setup_sets_hash_establishes_session_then_404s(env):
    _, client, tmp_path = env
    r = client.post("/liselott/satt-loesenord",
                    data={"loesenord": PASSWORD, "bekrafta": PASSWORD})
    assert r.status_code == 302
    assert r.headers["Location"] == "/liselott/"
    assert setting(tmp_path, "password_hash").startswith("$argon2id$")
    assert setting(tmp_path, "password_set_at")

    # she lands logged-in: GET / -> 200, not 302 (§6.1) — and it is the
    # shelf behind the owner nav, not the public landing (MC 12451).
    r = client.get("/liselott/")
    assert r.status_code == 200
    assert "Din hylla" in r.text

    # configured -> the setup route is gone forever (both methods)
    assert client.get("/satt-loesenord").status_code == 404
    assert client.post("/satt-loesenord",
                       data={"loesenord": PASSWORD, "bekrafta": PASSWORD}).status_code == 404


def test_post_after_window_refused_hash_unset(env, monkeypatch):
    _, client, tmp_path = env
    monkeypatch.setattr(auth, "START_TIME", time.time() - auth.SETUP_WINDOW_S - 1)
    r = client.post("/liselott/satt-loesenord",
                    data={"loesenord": PASSWORD, "bekrafta": PASSWORD})
    assert r.status_code == 403
    assert setting(tmp_path, "password_hash") is None  # nothing written
    assert setting(tmp_path, "password_set_at") is None


def test_closed_window_serves_gate_everywhere_zero_data(env, monkeypatch):
    _, client, _ = env
    monkeypatch.setattr(auth, "START_TIME", time.time() - auth.SETUP_WINDOW_S - 1)
    for path in ("/", "/bibliotek", "/logga-in", "/satt-loesenord", "/x"):
        r = client.get(path)
        assert "Inställningsfönstret är stängt." in r.text
        assert "Stöld" not in r.text  # zero app/seed bytes
    assert client.get("/healthz").status_code == 200


def test_healthz_200_in_every_state(env, monkeypatch):
    """P2-c: /healthz is 200 `ok` unconfigured+open, configured AND closed."""
    _, client, _ = env
    assert client.get("/healthz").status_code == 200
    assert client.get("/healthz").data == b"ok"          # open
    client.post("/liselott/satt-loesenord",
                data={"loesenord": PASSWORD, "bekrafta": PASSWORD})
    assert client.get("/healthz").data == b"ok"          # configured
    fresh = create_app()
    fresh.testing = True
    monkeypatch.setattr(auth, "START_TIME", time.time() - auth.SETUP_WINDOW_S - 1)
    r = fresh.test_client().get("/healthz")
    assert r.status_code == 200 and r.data == b"ok"      # closed window
