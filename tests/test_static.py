"""T4.4 — static files and cache-busting through the ONE mount mechanism.

Every asset URL this app emits must be prefix-absolute (§6.5 — the same
mechanism as every page URL, not a second one) AND carry `?v=<version>`, so a
deploy that changes the CSS cannot leave the owner's browser holding the old
one. The assertion is written over EVERY /static/ reference in a rendered page
rather than over the one stylesheet that exists today: when T5.3's script and
T7.3's self-hosted fonts land, they inherit this gate instead of escaping it."""
import subprocess
from pathlib import Path

import pytest

import app as app_module
from app import APP_VERSION, create_app

PASSWORD = "_test_losenord_"
ROOT = Path(__file__).resolve().parent.parent
CSS_HREF = 'href="/liselott/static/css/app.css?v='


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    flask_app = create_app()
    flask_app.testing = True
    return flask_app.test_client()


def head_sha():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True).stdout.strip()


# ── APP_VERSION ─────────────────────────────────────────────────────────────
def test_app_version_is_the_current_head():
    assert APP_VERSION == head_sha()


def test_app_version_falls_back_to_dev_outside_a_checkout(tmp_path):
    """No git, no crash: the app must still boot with an unversioned asset
    name (the fallback is a deploy shape, not an error path)."""
    assert app_module._read_version(cwd=tmp_path) == "dev"


def test_app_version_falls_back_when_git_is_unusable(monkeypatch, tmp_path):
    def boom(*a, **kw):
        raise OSError("no git here")
    monkeypatch.setattr(subprocess, "run", boom)
    assert app_module._read_version(cwd=tmp_path) == "dev"


# ── the emitted refs ────────────────────────────────────────────────────────
def test_css_href_is_prefixed_and_versioned(client):
    r = client.post("/liselott/satt-loesenord",
                    data={"loesenord": PASSWORD, "bekrafta": PASSWORD})
    page = client.get("/liselott/bibliotek")
    assert r.status_code == 302
    assert f'{CSS_HREF}{APP_VERSION}">' in page.text


def test_every_static_ref_in_the_page_carries_prefix_and_version(client):
    """The generic gate: a /static/ URL that forgot `?v=` — or the prefix —
    is exactly the bug this task exists to prevent."""
    client.post("/liselott/satt-loesenord",
                data={"loesenord": PASSWORD, "bekrafta": PASSWORD})
    refs = []
    for path in ("/liselott/bibliotek", "/liselott/sok", "/liselott/logga-in"):
        html = client.get(path).get_data(as_text=True)
        assert client.get(path).status_code == 200, path
        refs += [(path, url) for url in _static_urls(html)]
    assert refs, "no static refs at all — the gate would be vacuous"
    for path, url in refs:
        assert url.startswith("/liselott/static/"), (path, url)
        assert "v=" in url, (path, url)


def _static_urls(html):
    import re
    return re.findall(r'(?:href|src)="([^"]*?/static/[^"]*)"', html)


def test_stylesheet_is_served_and_is_css(client):
    r = client.get("/liselott/static/css/app.css")
    assert r.status_code == 200
    assert r.mimetype == "text/css"
    assert "bok-kort" in r.get_data(as_text=True)


def test_static_needs_no_session_but_a_version_never_reaches_the_fs(client):
    """§6.4 allow-listing stays: anonymous static is 200/404, never a redirect;
    and `v` is a query param, not a path — a crafted v cannot walk the FS."""
    assert client.get("/liselott/static/css/app.css").status_code == 200
    assert client.get("/liselott/static/ingenting.css").status_code == 404
    r = client.get("/liselott/static/css/app.css", query_string={
        "v": "../../../etc/passwd"})
    assert r.status_code == 200
    assert b"root:" not in r.data


def test_custom_prefix_reaches_the_asset_url_too(tmp_path, monkeypatch):
    """The mount mechanism is ONE mechanism: move the app, and the asset URL
    moves with it — nothing in the template hardcodes /liselott."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LISELOTT_PREFIX", "/testmonly")
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    flask_app = create_app()
    flask_app.testing = True
    c = flask_app.test_client()
    # the setup page (the app is unconfigured here, so /logga-in 302s per §6.1)
    # extends the SAME base.html, and its asset URL carries the new prefix
    page = c.get("/testmonly/satt-loesenord")
    assert page.status_code == 200
    assert 'href="/testmonly/static/css/app.css?v=' in page.text
    assert "/liselott/static/" not in page.text
