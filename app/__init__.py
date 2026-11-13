"""Liselotts bokhylla — app factory (§6.3 cookie defaults, §6.5 mount
middleware, §9 cache-busted assets)."""
import os
import subprocess
from pathlib import Path

from flask import Flask, request

DEFAULT_PREFIX = "/liselott"
REPO_ROOT = Path(__file__).resolve().parent.parent

# §9 + M8-hotfix-3 (MC 12451): every asset URL already carries ?v=<version>,
# so the bytes behind one URL never change and the correct pairing is a year
# of `immutable`. Left to Flask's 12 h default, Cloudflare applies its OWN 4 h
# policy to .css and froze a wrong body under app.css for the whole TTL —
# the header has to say what the version key already guarantees.
STATIC_CACHE_CONTROL = "public, max-age=31536000, immutable"
PINNABLE_STATUSES = (200, 206, 304)


def _read_version(cwd=None):
    """T4.4: the deployed code is immutable, so the commit IS a perfect cache
    key. No git (an unpacked deploy, a shallow CI tree) is NOT an error: the
    tree's own VERSION file is the key then, and only when THAT is missing too
    does the app boot with the literal "dev" (M8-hotfix-3, MC 12451: the vm106
    mirror carries no .git, so prod ran on "dev" and every deploy emitted the
    SAME ?v= — a poisoned asset URL survived the deploy that fixed it). A
    deploy that changes assets bumps VERSION, in the same commit."""
    root = Path(cwd or REPO_ROOT)
    try:
        proc = subprocess.run(["git", "rev-parse", "HEAD"],
                              cwd=str(root), capture_output=True,
                              text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        proc = None
    if proc is not None and proc.returncode == 0:
        sha = proc.stdout.strip()
        if len(sha) == 40:
            return sha
    try:
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "dev"  # no git, no VERSION: the old unversioned shape
    return version or "dev"


# Read ONCE at import: a deploy restarts the process, so this cannot go stale
# under a long-running app, and no request ever shells out to git.
APP_VERSION = _read_version()


def current_prefix():
    return os.environ.get("LISELOTT_PREFIX", DEFAULT_PREFIX)


def mount_middleware(wsgi_app):
    """§6.5 — the single mount-prefix mechanism (F-3).

    SCRIPT_NAME is ALWAYS set to PREFIX so url_for/redirects/static emit
    prefix-absolute URLs; a leading PREFIX in PATH_INFO is stripped, so both
    the bare shape nginx delivers (trailing-slash proxy_pass) and the
    prefixed shape route identically (fest40 L137/L143 pattern).
    """
    prefix = current_prefix().rstrip("/")

    def wrapped(environ, start_response):
        environ["SCRIPT_NAME"] = prefix
        path = environ.get("PATH_INFO", "")
        if path == prefix:
            environ["PATH_INFO"] = "/"
        elif path.startswith(prefix + "/"):
            environ["PATH_INFO"] = path[len(prefix):]
        return wsgi_app(environ, start_response)

    return wrapped


def create_app():
    app = Flask(__name__)
    app.config.update(
        # §6.3 — cookie contract; Secure ON unless LISELOTT_ENV=dev (unset = production).
        SESSION_COOKIE_NAME="liselott_session",
        SESSION_COOKIE_PATH=current_prefix(),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("LISELOTT_ENV") != "dev",
    )
    # §9/T4.4: the asset version is a template global, so every ref in every
    # template is url_for(..., v=APP_VERSION) — never a hand-written ?v=.
    app.jinja_env.globals["APP_VERSION"] = APP_VERSION
    app.wsgi_app = mount_middleware(app.wsgi_app)

    @app.after_request
    def _pin_static_cache(response):
        """§9/M8-hotfix-3: the versioned asset URL is immutable, so say so on
        the response. Only a served body is pinned — Cloudflare caches 404s
        for static-looking URLs by default too, and pinning a miss would
        freeze the absence for a year (the same class of bug, mirrored)."""
        if (request.endpoint == "static"
                and response.status_code in PINNABLE_STATUSES):
            response.headers["Cache-Control"] = STATIC_CACHE_CONTROL
        return response

    # Late import: app.auth imports app.db, never the factory (no cycle).
    from app import (auth, backfill, bundle, onska, redigera, report,
                         routes, tillagg)
    auth.init_auth(app)
    routes.init_routes(app)
    redigera.init_redigera(app)
    tillagg.init_tillagg(app)
    onska.init_onska(app)
    report.init_report(app)
    backfill.init_backfill(app)
    bundle.init_bundle(app)

    @app.get("/healthz")
    def healthz():
        return "ok"

    return app
