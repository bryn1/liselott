"""Liselotts bokhylla — app factory (§6.3 cookie defaults, §6.5 mount middleware)."""
import os

from flask import Flask

DEFAULT_PREFIX = "/liselott"


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
    app.wsgi_app = mount_middleware(app.wsgi_app)

    # Late import: app.auth imports app.db, never the factory (no cycle).
    from app import auth, routes
    auth.init_auth(app)
    routes.init_routes(app)

    @app.get("/healthz")
    def healthz():
        return "ok"

    return app
