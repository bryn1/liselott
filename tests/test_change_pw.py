"""T2.7 — change password + session kill (§6.7): logged-in rotation stores a
new argon2 hash, regenerates secret.key (0600) and re-assigns app.secret_key,
so EVERY old session cookie dies (next GET 302); re-login with the new password
works; wrong current password 401s without touching anything.
scripts/reset_password.py (VM350/dev use only — production has no shell, §12)
keeps working against state_base()."""
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app import create_app

ROOT = Path(__file__).resolve().parent.parent
OLD = "_gammal_losenord_"
NEW = "_nya_losenordet_"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    app = create_app()
    app.testing = True

    @app.route("/")
    def _root_stub():
        return "rot", 200

    client = app.test_client()
    r = client.post("/liselott/satt-loesenord",
                    data={"loesenord": OLD, "bekrafta": OLD})
    assert r.status_code == 302
    return app, client, tmp_path


def setting(tmp_path, key):
    conn = sqlite3.connect(tmp_path / "liselott.db")
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row[0] if row else None


def token(client):
    with client.session_transaction("/liselott/logga-in") as sess:
        return sess["csrf"]


def change(client, current, new, confirm, *, csrf=None):
    return client.post("/liselott/byter-losenord", data={
        "nuvarande": current, "ny": new, "ny_bekrafta": confirm,
        "csrf": token(client) if csrf is None else csrf})


def test_change_requires_token(env):
    _, client, _ = env
    r = client.post("/liselott/byter-losenord",
                    data={"nuvarande": OLD, "ny": NEW, "ny_bekrafta": NEW})
    assert r.status_code == 400  # browser form route: CSRF token applies


def test_change_password_rotates_hash_secret_kills_sessions(env):
    _, client, tmp_path = env
    old_hash = setting(tmp_path, "password_hash")
    prev_signing_key = (tmp_path / "secret.key").read_text()
    r = change(client, OLD, NEW, NEW)
    assert r.status_code == 302
    assert r.headers["Location"] == "/liselott/logga-in"
    new_hash = setting(tmp_path, "password_hash")
    assert new_hash != old_hash and new_hash.startswith("$argon2id$")
    assert setting(tmp_path, "password_set_at")
    assert (tmp_path / "secret.key").read_text() != prev_signing_key
    # every old cookie dies (§6.7): the owner surfaces are back behind the
    # guard (writing is private — MC 12497)…
    r = client.get("/liselott/onska")
    assert (r.status_code, r.headers["Location"]) == (302, "/liselott/logga-in")
    # …the public shelf READS 200 to the dead cookie like any stranger's,
    # and paints no owner UI…
    r = client.get("/liselott/bibliotek")
    assert r.status_code == 200 and "Logga ut" not in r.text
    # …and the root answers its public landing again, not the shelf (MC 12451)
    r = client.get("/liselott/")
    assert r.status_code == 200 and "Din hylla" not in r.text
    # re-login with the new password works
    r = client.post("/liselott/logga-in", data={"loesenord": NEW})
    assert r.status_code == 302
    r = client.get("/liselott/")
    assert r.status_code == 200 and "Din hylla" in r.text  # the shelf again


def test_wrong_current_401_changes_nothing(env):
    _, client, tmp_path = env
    old_hash = setting(tmp_path, "password_hash")
    prev_signing_key = (tmp_path / "secret.key").read_text()
    r = change(client, "fel-gammalt-losenord", NEW, NEW)
    assert r.status_code == 401
    assert setting(tmp_path, "password_hash") == old_hash
    assert (tmp_path / "secret.key").read_text() == prev_signing_key
    r = client.get("/liselott/")
    assert r.status_code == 200 and "Din hylla" in r.text  # session survives


def test_new_password_validation(env):
    _, client, tmp_path = env
    old_hash = setting(tmp_path, "password_hash")
    r = change(client, OLD, "kort", "kort")
    assert r.status_code == 400 and "fel-meddelande" in r.text
    r = change(client, OLD, NEW, "annat")
    assert r.status_code == 400 and "fel-meddelande" in r.text
    assert setting(tmp_path, "password_hash") == old_hash


def test_reset_password_script_against_state_base(tmp_path, monkeypatch):
    """scripts/reset_password.py runs against state_base() via the dev/build
    env override and the new password logs in through the real route."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    # subprocess inherits the patched env → state_base() resolves to tmp_path
    r = subprocess.run([sys.executable, str(ROOT / "scripts/reset_password.py"), NEW],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    app = create_app()
    app.testing = True

    @app.route("/")
    def _root_stub():
        return "rot", 200

    client = app.test_client()
    assert client.post("/liselott/logga-in", data={"loesenord": OLD}).status_code == 401
    assert client.post("/liselott/logga-in", data={"loesenord": NEW}).status_code == 302
    r = client.get("/liselott/")
    assert r.status_code == 200 and "Din hylla" in r.text  # the shelf, logged in
