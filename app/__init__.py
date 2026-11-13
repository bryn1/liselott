"""Liselotts bokhylla — app factory (§6.3 cookie defaults, §6.5 mount
middleware, §9 cache-busted assets)."""
import os
import subprocess
from pathlib import Path

from flask import Flask

DEFAULT_PREFIX = "/liselott"
REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_version(cwd=None):
    """T4.4: the deployed code is immutable, so the commit IS a perfect cache
    key. No git (an unpacked deploy, a shallow CI tree) is NOT an error — the
    app boots with the literal "dev" and ships unversioned asset names."""
    try:
        proc = subprocess.run(["git", "rev-parse", "HEAD"],
                              cwd=str(cwd or REPO_ROOT), capture_output=True,
                              text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return "dev"
    sha = proc.stdout.strip()
    if proc.returncode != 0 or len(sha) != 40:
        return "dev"
    return sha


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

    # Late import: app.auth imports app.db, never the factory (no cycle).
    from app import auth, redigera, routes
    auth.init_auth(app)
    routes.init_routes(app)
    redigera.init_redigera(app)

    @app.get("/healthz")
    def healthz():
        return "ok"

    return app
