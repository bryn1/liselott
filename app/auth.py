"""Auth core (§6) — setup window, guard allow-list, mount-aware redirects.
The §6.1 three-state matrix is pinned here (P2-c): /healthz answers 200 `ok`
in EVERY state; /satt-loesenord exists only while the password is unset AND
within SETUP_WINDOW_S of process start (F-5: no public land-grab — fest40
20-min-window parity); once configured it 404s forever. Rate limit (§6.2) and
CSRF (§6.6) extend this same guard in T2.4/T2.5."""
import os
import time
from datetime import datetime, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from flask import abort, redirect, render_template, request, session

from app import db

# §6.1 constants. START_TIME is a module attribute read AT REQUEST TIME so the
# window negatives can age it (fest40 REGISTER_WINDOW_S parity, VERIFIED L47).
SETUP_WINDOW_S = 20 * 60
START_TIME = time.time()
PASSWORD_MIN = 10
SESSION_FLAG = "inloggd"

# §6.4 exhaustive unauthenticated allow-list (P2-7); nothing else answers an
# anonymous request, and /satt-loesenord within it is further gated by state.
UNAUTHENTICATED_ALLOW = ("/healthz", "/logga-in", "/satt-loesenord", "/robots.txt")
STATIC_PREFIX = "/static/"

_hasher = PasswordHasher()  # argon2id by default (§6.1)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_setting(conn, key):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_setting(conn, key, value):
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value))
    conn.commit()


def is_configured(conn) -> bool:
    return get_setting(conn, "password_hash") is not None


def window_open() -> bool:
    return (time.time() - START_TIME) < SETUP_WINDOW_S


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored: str, password: str) -> bool:
    try:
        return _hasher.verify(stored, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def ensure_secret() -> str:
    """Flask session key: state_dir/secret.key, 0600, created first boot (§4).
    Read per request so /byter-losenord regeneration (§6.7) kills old session
    cookies with no cache to invalidate."""
    path = db.state_base() / "secret.key"
    if not path.exists():
        path.write_bytes(os.urandom(32).hex().encode())
        os.chmod(path, 0o600)
    return path.read_text(encoding="utf-8")


def _to(path: str):
    """Redirect keeping the §6.5 mount: SCRIPT_NAME is always PREFIX, so
    script_root + path is already prefix-absolute."""
    return redirect((request.script_root or "") + path)


def _establish_session():
    session.clear()
    session[SESSION_FLAG] = True


def _closed_gate():
    """Closed-window state (§6.1): zero app data answered; POST setup -> 403."""
    if request.path == "/healthz":
        return None
    if request.path == "/satt-loesenord" and request.method == "POST":
        return render_template("stangd.html"), 403
    return render_template("stangd.html")


def init_auth(app):
    # Flask opens the session at request-context push, BEFORE before_request
    # hooks — so the key from secret.key (0600, first boot, §4) must be on the
    # app at creation. /byter-losenord (§6.7) regenerates the file AND
    # re-assigns app.secret_key; single-process production keeps both in step.
    app.secret_key = ensure_secret()
    app.teardown_appcontext(db.close_db)

    @app.before_request
    def _auth_gate():
        # §6.5: PATH_INFO reaches Flask already prefix-stripped, so request.path
        # is the bare route path in both request shapes.
        conn = db.get_db()
        if not is_configured(conn):
            if not window_open():
                return _closed_gate()
            if request.path == "/logga-in":
                return _to("/satt-loesenord")  # §6.1 open state
            if (request.path in ("/healthz", "/satt-loesenord", "/robots.txt")
                    or request.path.startswith(STATIC_PREFIX)):
                return None
            return _to("/satt-loesenord")
        if request.path == "/satt-loesenord":
            abort(404)  # configured -> gone forever (§6.1)
        if request.path in UNAUTHENTICATED_ALLOW or request.path.startswith(STATIC_PREFIX):
            return None
        if session.get(SESSION_FLAG):
            return None
        return _to("/logga-in")

    @app.errorhandler(404)
    def _not_found(err):
        # Unmatched paths never reach before_request; the closed-window gate
        # still answers every route except /healthz (§6.1). Other states' 404
        # pages render no data (§6.4).
        conn = db.get_db()
        if not is_configured(conn) and not window_open():
            return render_template("stangd.html"), 404
        return err

    @app.route("/satt-loesenord", methods=["GET", "POST"])
    def satt_losenord():
        # The guard lets this through ONLY unconfigured+window-open.
        if request.method == "GET":
            return render_template("satt-losenord.html", fel=None)
        conn = db.get_db()
        pw = request.form.get("loesenord", "")
        if len(pw) < PASSWORD_MIN:
            return render_template(
                "satt-losenord.html",
                fel=f"Lösenordet måste vara minst {PASSWORD_MIN} tecken."), 400
        if pw != request.form.get("bekrafta", ""):
            return render_template(
                "satt-losenord.html", fel="Lösenorden matchar inte."), 400
        set_setting(conn, "password_hash", hash_password(pw))
        set_setting(conn, "password_set_at", utcnow_iso())
        _establish_session()  # she lands logged-in (§6.1)
        return _to("/")
