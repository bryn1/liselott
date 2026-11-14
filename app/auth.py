"""Auth core (§6) — setup window, guard allow-list, mount-aware redirects.
The §6.1 three-state matrix is pinned here (P2-c): /healthz answers 200 `ok`
in EVERY state; /satt-loesenord exists only while the password is unset AND
within SETUP_WINDOW_S of process start (F-5: no public land-grab — fest40
20-min-window parity); once configured it 404s forever. Rate limit (§6.2) and
CSRF (§6.6) extend this same guard in T2.4/T2.5."""
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

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

# §6.2 (P2-1): 5 failures / 15 min -> 429; rows older than 1 h pruned on every
# check. POST /satt-loesenord shares this bucket (§6.1).
MAX_ATTEMPTS = 5
ATTEMPT_WINDOW_S = 15 * 60
ATTEMPT_RETENTION_S = 60 * 60
TOO_MANY_COPY = "För många försök — försök igen om en kvart."

# §6.4 exhaustive unauthenticated allow-list (P2-7), widened by EXACTLY one
# leg (M8 staging gate, MC 12451): the product path GET /liselott/ must
# answer 200 with a public landing like the three live service apps
# (measured 2026-11-13: fest40 200/1815 B, matapp 200/12388 B, klartx
# 200/4056 B) — a login-gated app's root is a landing, not a redirect. The
# root joins as a READS-ONLY leg (_is_public_root below); its page is fixed
# copy with zero app data (app/templates/start.html), and /satt-loesenord
# within the list is further gated by state. Data routes joined this posture
# through _is_public_read (MC 12497) when the site got its public-read
# contract — see the constants below.
UNAUTHENTICATED_ALLOW = ("/healthz", "/logga-in", "/satt-loesenord", "/robots.txt")
STATIC_PREFIX = "/static/"
PUBLIC_ROOT = "/"
READ_METHODS = ("GET", "HEAD")

# MC 12497 (owner ruling 2026-11-14, verbatim): "The website
# sibbamala.com/liselott should be public. All rate books should be public.
# Rating and whishing is blocked behind liselotts password" => reading is
# public, writing stays behind the one owner session. The list IS the DoD
# matrix: shelf, bok page, search, the rec surface and covers answer an
# anonymous READ (plus the root landing + static, which the M8 gate already
# widened). The owner surfaces are deliberately NOT here — /onska,
# /lagg-till, /redigera, /rapa, /backup, /byter-losenord stay behind the
# session exactly as every POST does. Setup-state exception: this rule is
# consulted in the CONFIGURED branch of _auth_gate only — while no password
# is set the choose-password gate wraps the whole site as before.
PUBLIC_READ_PATHS = ("/", "/bibliotek", "/sok", "/rekommendationer")
PUBLIC_READ_PREFIXES = ("/bok/", "/cover/")

# F-F2 (DA-verdict-c2, MC 12451): the _file_shaped() dot heuristic has
# exactly one known miss — VERSION, the extension-less repo-root file the
# lane mirror carries (hotfix-3's own cache key). The staging gate probes it
# like the dotted names, and live it fingerprinted the gate (anonymous 302,
# closed state 200 gate page). Named beside the rule instead of widening
# the rule: a bare name, not a route or asset spelling, keeps landing,
# /static and every allow-listed path exactly as they were.
QUARANTINED_DOTTED_LESS = ("VERSION",)

# §6.6 + P2-r4 (DA-verdict-c3 Part 3): state-change methods carry the CSRF
# rule. TOKENLESS_POSTS are checked by ORIGIN ONLY — the machine trio per
# §6.6's curl posture, and /logga-in + /satt-loesenord per P2-r4 so the runbook
# T8.5 tokenless curl login ("curl -X POST -d loesenord=… /logga-in", no GET
# first, so no session could ever carry a token) stays true as written. The
# exemption is TOKENLESS, not guardless: foreign Origin still 400s and the
# routes keep their own guards (rate limit + password / window + rate limit).
CSRF_METHODS = ("POST", "PUT", "PATCH", "DELETE")
TOKENLESS_POSTS = ("/logga-in", "/satt-loesenord", "/seed", "/bundle", "/backfill")
CSRF_TOKEN_COPY = "Säkerhetsmärket saknas — ladda om sidan och försök igen."
FOREIGN_ORIGIN_COPY = "Fel — formuläret skickades från en annan webbplats."

_hasher = PasswordHasher()  # argon2id by default (§6.1)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ago_iso(seconds: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def client_ip(req) -> str:
    """§6.2 (P2-1) with the trust order RE-DRAWN by F-4 (SEC-verdict-12497):
    CF-Connecting-IP when present — the Cloudflare edge OVERWRITES any
    client-supplied spelling of it on a proxied zone, so on the internet
    path that header IS the edge's own value — else the SOCKET PEER
    (REMOTE_ADDR). X-Forwarded-For is NOT consulted at all: at this origin
    every request that can reach the port writes that header itself, and
    the verdict measured a spoofed one hopping buckets past an exhausted
    5/15-min bucket straight into password verification. The renderer
    whose LAST hop the old rule trusted is not this app's path (§6.5: the
    edge forwards to this port; the vm106 origin port is LAN-side). The
    residual is documented and accepted: whoever can reach the port
    directly can still rotate buckets via CF-Connecting-IP."""
    cf = req.headers.get("CF-Connecting-IP")
    if cf:
        return cf.strip()
    return req.remote_addr or ""


def _limit_reached(conn, ip: str) -> bool:
    conn.execute("DELETE FROM login_attempts WHERE ts < ?",
                 (_ago_iso(ATTEMPT_RETENTION_S),))  # prune (§6.2)
    conn.commit()
    row = conn.execute(
        "SELECT COUNT(*) FROM login_attempts WHERE ip = ? AND ts >= ?",
        (ip, _ago_iso(ATTEMPT_WINDOW_S))).fetchone()
    return row[0] >= MAX_ATTEMPTS


def _record_attempt(conn, ip: str):
    conn.execute("INSERT INTO login_attempts (ip, ts) VALUES (?, ?)",
                 (ip, utcnow_iso()))
    conn.commit()


def _clear_attempts(conn, ip: str):
    conn.execute("DELETE FROM login_attempts WHERE ip = ?", (ip,))
    conn.commit()


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


def redirect_prefixed(path: str):
    """Redirect keeping the §6.5 mount: SCRIPT_NAME is always PREFIX, so
    script_root + path is already prefix-absolute."""
    return redirect((request.script_root or "") + path)


def _establish_session():
    session.clear()
    session[SESSION_FLAG] = True
    session["csrf"] = secrets.token_urlsafe(32)  # session-bound form token


def rotate_secret(app):
    """§6.7: regenerate secret.key (0600) AND re-assign app.secret_key —
    single-process production makes every existing session cookie die with no
    cache to invalidate; the owner lands back at /logga-in."""
    path = db.state_base() / "secret.key"
    path.write_bytes(os.urandom(32).hex().encode())
    os.chmod(path, 0o600)
    app.secret_key = path.read_text(encoding="utf-8")


def _is_public_root() -> bool:
    """The §6.4 landing leg: the ROOT itself, reads only — every other
    method on / keeps facing the guard's old answer (MC 12451). The
    configured branch does not need this rule any more (the root is one of
    PUBLIC_READ_PATHS, MC 12497); it stands for the fresh-state landing,
    where the choose-password gate still wraps everything else."""
    return request.path == PUBLIC_ROOT and request.method in READ_METHODS


def _is_public_read() -> bool:
    """MC 12497 (owner ruling 2026-11-14): the public-read contract of a
    CONFIGURED site — shelf, bok page, search, rec surface, covers and the
    root answer an anonymous READ. READ_METHODS only: a POST to a read path
    stays the guard's refuse, the same non-2xx the route contract pins for
    every anonymous write.
    F-3 (SEC-verdict-12497): the match tolerates the ONE trailing slash.
    werkzeug 3.1 REMOVED the strict-slash redirect (this pin has no
    RequestRedirect — probed), so nothing else normalizes the spelling
    either: guarding the bare string sent a shared /bibliotek/ to the
    login wall, and guarding it alone would trade that for the router's
    404. The public views therefore registered their slash-spelling rule
    beside the canonical one (routes.py, F-3) — an explicit rule, not a
    redirect mechanism beside Flask's — and the tolerated spelling answers
    the page itself, 200. The method rule runs FIRST, so a POST /bibliotek/
    keeps the guard's refuse."""
    if request.method not in READ_METHODS:
        return False
    path = request.path
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return path in PUBLIC_READ_PATHS or path.startswith(PUBLIC_READ_PREFIXES)


def _file_shaped() -> bool:
    """M8-hotfix-2 (MC 12451): the lane staging gate (vm106-staging-gate.sh
    §6) probes every root file the mirror DROPS (DESIGN.md, README.md,
    LEDGER.md, hosting.yaml, data-import/*.csv, server.py …) and passes a
    quarantined name only on 404/403 — a 302 fingerprints the auth gate and
    reads as "reachable". A final path segment carrying a dot is a
    file-shaped name, and the ONE quarantined dotted-less name
    (QUARANTINED_DOTTED_LESS, F-F2) counts too; the guard asks this ONLY on
    its unauthenticated redirect branches, so allow-listed routes
    (/robots.txt has a dot) and /static/ are already through. The answer is
    abort(404) — the SAME errorhandler an owner gets (routes.py: 404.html,
    plain Swedish copy, zero app data, no hint of why), so anonymous and
    logged-in 404s are indistinguishable and leak nothing. Extension-less
    unknown paths keep the §6.4 uniform 302 (the T2.6 contract — not
    churned)."""
    last = request.path.rsplit("/", 1)[-1]
    return "." in last or last in QUARANTINED_DOTTED_LESS


def _closed_gate():
    """Closed-window state (§6.1): zero app data answered; POST setup -> 403.
    M8-hotfix-3 (MC 12451): /static/ is allowed through FIRST, exactly as in
    the two open states — it is zero-personal-data by construction (css/js/
    fonts/placeholder svg), the same argument §6.4's allow-list already makes.
    Serving the gate PAGE under an asset URL is what poisoned the live site:
    Cloudflare caches .css-extension responses 4 h by default and froze 378 B
    of gate HTML under app.css, so the landing rendered unstyled until the TTL
    expired. F-E/F-F (MC 12451) make the staging posture STATE-INVARIANT:
    the quarantined file-shaped names — and with them §6.4's dotted
    /robots.txt leg, named a second time beside the rule that already covers
    it — 404 BEFORE the gate page renders, exactly as in the open states;
    a probe must read 404/403 for those names in EVERY state, a 200 reads
    "reachable". Everything else shapeless keeps the §6.1-pinned gate
    page."""
    if request.path == "/healthz":
        return None
    if request.path.startswith(STATIC_PREFIX):
        return _csrf_gate()
    if _file_shaped() or request.path == "/robots.txt":
        abort(404)  # the SAME indistinguishable 404 the open states emit
    if request.path == "/satt-loesenord" and request.method == "POST":
        return render_template("stangd.html"), 403
    return render_template("stangd.html")


def _origin_refused():
    """§6.6's same-origin rule, the half every CSRF-checked method gets: a
    MISSING Origin (curl) passes, a foreign one 400s."""
    origin = request.headers.get("Origin")
    if origin and urlsplit(origin).netloc.lower() != request.host.lower():
        return render_template("csrf-fel.html", fel=FOREIGN_ORIGIN_COPY), 400
    return None


def _csrf_gate():
    """§6.6 — runs for every ALLOWED state-change request (the guard's login
    check happens first; unauth POSTs 302 before ever reaching here).
    Missing Origin (curl) passes, foreign Origin 400s; token required on every
    state change except the TOKENLESS_POSTS routes above.
    F-1 (SEC-verdict-12497): HEAD used to skip this gate entirely — it no
    longer does. HEAD gets the ORIGIN rule, the same one POST has always
    had (the verdict's cross-site browser-HEAD scenario is dead on it: a
    browser attaches Origin to every cross-origin fetch). The TOKEN rule
    stays a CSRF_METHODS rule on purpose: HEAD is READ_METHODS to the guard,
    processes nothing since the POST-only views, and token-checking a HEAD
    would 400 the anonymous public reads MC 12497 just made public."""
    if request.method == "HEAD":
        return _origin_refused()
    if request.method not in CSRF_METHODS:
        return None
    refused = _origin_refused()
    if refused is not None:
        return refused
    if request.path in TOKENLESS_POSTS:
        return None
    sent = request.form.get("csrf") or request.headers.get("X-CSRF-Token", "")
    if not sent or sent != session.get("csrf"):
        return render_template("csrf-fel.html", fel=CSRF_TOKEN_COPY), 400
    return None


def init_auth(app):
    # Flask opens the session at request-context push, BEFORE before_request
    # hooks — so the key from secret.key (0600, first boot, §4) must be on the
    # app at creation. /byter-losenord (§6.7) regenerates the file AND
    # re-assigns app.secret_key; single-process production keeps both in step.
    app.secret_key = ensure_secret()
    app.teardown_appcontext(db.close_db)
    # Forms (T2.7 onward) render csrf_token() into a hidden `csrf` field —
    # the value _csrf_gate() compares against the session (§6.6).
    app.jinja_env.globals.setdefault(
        "csrf_token", lambda: session.get("csrf", ""))

    @app.before_request
    def _auth_gate():
        # §6.5: PATH_INFO reaches Flask already prefix-stripped, so request.path
        # is the bare route path in both request shapes.
        conn = db.get_db()
        if not is_configured(conn):
            if not window_open():
                return _closed_gate()
            if request.path == "/logga-in":
                return redirect_prefixed("/satt-loesenord")  # §6.1 open state
            if (request.path in ("/healthz", "/satt-loesenord", "/robots.txt")
                    or _is_public_root()
                    or request.path.startswith(STATIC_PREFIX)):
                return _csrf_gate()
            if _file_shaped():
                abort(404)  # quarantined file names 404, never 302 (M8-fix2)
            return redirect_prefixed("/satt-loesenord")
        if request.path == "/satt-loesenord":
            abort(404)  # configured -> gone forever (§6.1)
        if (request.path in UNAUTHENTICATED_ALLOW or _is_public_read()
                or request.path.startswith(STATIC_PREFIX)):
            return _csrf_gate()
        if session.get(SESSION_FLAG):
            return _csrf_gate()
        if _file_shaped():
            abort(404)  # quarantined file names 404, never 302 (M8-fix2)
        return redirect_prefixed("/logga-in")

    @app.get("/robots.txt")
    def robots():
        # §6.4/MC 12497 (owner ruling 2026-11-14): a CONFIGURED site is
        # public to read, so crawlers are allowed in. The write paths keep
        # their refuse no matter what a crawler is served here. While no
        # password is set the choose-password gate still wraps the site
        # (the setup-state exception), and the honest answer stays
        # Disallow. The closed window never reaches this view: the guard
        # 404s this name in every state (F-F, MC 12451).
        body = "Allow: /\n" if is_configured(db.get_db()) else "Disallow: /\n"
        return body, 200, {"Content-Type": "text/plain; charset=utf-8"}

    @app.route("/logga-in", methods=["GET", "POST"])
    def logga_in():
        # Unauthenticated-reachable per §6.4; the guard redirects here when a
        # session is required. The token exemption for this POST (P2-r4: the
        # runbook T8.5 curl login carries no session, no token) is built in
        # T2.5 as the same-origin-only machine rule.
        # F-1 (SEC-verdict-12497): POST is the ONLY processing method. The
        # old split rendered on GET and processed "everything else", so a
        # HEAD executed this state change with no token and no Origin check:
        # five wrong-password HEADs drained the §6.2 bucket and locked the
        # owner out of her NEXT real login (the limit precedes verification),
        # and a HEAD+body could log in. Every other method gets the read the
        # route advertises; PUT/PATCH/DELETE never reach the view (routing).
        if request.method != "POST":
            return render_template("logga-in.html", fel=None)
        conn = db.get_db()
        ip = client_ip(request)
        if _limit_reached(conn, ip):
            # checked BEFORE password verification: correct pw inside the
            # window is still 429 (T2.4)
            return render_template("logga-in.html", fel=TOO_MANY_COPY), 429
        stored = get_setting(conn, "password_hash")
        if not stored or not verify_password(stored, request.form.get("loesenord", "")):
            _record_attempt(conn, ip)
            return render_template("logga-in.html", fel="Fel lösenord."), 401
        _clear_attempts(conn, ip)
        _establish_session()
        return redirect_prefixed("/")

    @app.get("/logga-ut")
    def logga_ut():
        session.clear()
        return redirect_prefixed("/logga-in")

    @app.route("/satt-loesenord", methods=["GET", "POST"])
    def satt_losenord():
        # The guard lets this through ONLY unconfigured+window-open.
        # F-1 (SEC-verdict-12497): POST-only processing, as in logga_in —
        # a HEAD+body in the setup window used to SET THE PASSWORD here,
        # anonymous, no CSRF machinery anywhere in sight.
        if request.method != "POST":
            return render_template("satt-losenord.html", fel=None)
        conn = db.get_db()
        ip = client_ip(request)
        if _limit_reached(conn, ip):
            # §6.1: shares the login_attempts bucket — validation rejections
            # count as attempts; the window bounds exposure further.
            return render_template("satt-losenord.html", fel=TOO_MANY_COPY), 429
        pw = request.form.get("loesenord", "")
        if len(pw) < PASSWORD_MIN:
            _record_attempt(conn, ip)
            return render_template(
                "satt-losenord.html",
                fel=f"Lösenordet måste vara minst {PASSWORD_MIN} tecken."), 400
        if pw != request.form.get("bekrafta", ""):
            _record_attempt(conn, ip)
            return render_template(
                "satt-losenord.html", fel="Lösenorden matchar inte."), 400
        _clear_attempts(conn, ip)
        set_setting(conn, "password_hash", hash_password(pw))
        set_setting(conn, "password_set_at", utcnow_iso())
        _establish_session()  # she lands logged-in (§6.1)
        return redirect_prefixed("/")
