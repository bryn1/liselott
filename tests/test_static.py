"""T4.4 — static files and cache-busting through the ONE mount mechanism.

Every asset URL this app emits must be prefix-absolute (§6.5 — the same
mechanism as every page URL, not a second one) AND carry `?v=<version>`, so a
deploy that changes the CSS cannot leave the owner's browser holding the old
one. The assertion is written over EVERY /static/ reference in a rendered page
rather than over the one stylesheet that exists today: when T5.3's script and
T7.3's self-hosted fonts land, they inherit this gate instead of escaping it."""
import re
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
def test_app_version_is_the_current_head(client):
    """Sync claim (repo↔build) — scoped to where git can actually answer.
    `git rev-parse HEAD` in a git-free tree (the sealed-rerun `git archive`
    shape, the vm106 mirror) exits non-zero with empty/"HEAD" on stdout, so
    there is no HEAD to sync against: there the BOOT claim stands instead
    (M8-hotfix-3) — a well-formed VERSION stamp, not "dev", and it reaches
    the emitted asset URL. The branch mirrors _read_version's own predicate:
    git counts only when it printed a sha; anything else is the fallback
    shape the sibling legs below pin down."""
    sha = head_sha()
    if re.fullmatch(r"[0-9a-f]{40}", sha):
        assert APP_VERSION == sha
        return
    assert re.fullmatch(r"\d{4}\.\d{1,2}-\d+", APP_VERSION), APP_VERSION
    r = client.post("/liselott/satt-loesenord",
                    data={"loesenord": PASSWORD, "bekrafta": PASSWORD})
    page = client.get("/liselott/bibliotek")
    assert r.status_code == 302
    assert f'{CSS_HREF}{APP_VERSION}">' in page.text


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


# ── T7.3 — self-hosted Lora (§9 "type": one serif voice, 400/700, swap) ─────
FONTS = ("lora-400.woff2", "lora-700.woff2")


def test_css_declares_lora_faces_with_swap():
    """§9's voice is Lora 400/700 self-hosted: two @font-face blocks, the
    weights the stylesheet's --font stack asks for, and font-display: swap so
    text is never invisible while the font loads."""
    css = (ROOT / "app" / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert css.count("@font-face") == 2
    assert "font-display: swap" in css
    for weight in ("400", "700"):
        block = re.search(r"@font-face\s*\{[^}]*font-weight:\s*%s[^}]*\}" % weight, css)
        assert block, f"no @font-face for weight {weight}"
        assert f"../fonts/lora-{weight}.woff2" in css, \
            f"weight {weight} does not reference ../fonts/lora-{weight}.woff2"


def test_font_files_are_served_and_are_woff2(client):
    """Served 200 under the mount prefix, and actually woff2 bytes (magic
    wOF2) — a 200 from a fallback page would pass status but not this."""
    for name in FONTS:
        r = client.get(f"/liselott/static/fonts/{name}")
        assert r.status_code == 200, name
        assert r.data[:4] == b"wOF2", name


def test_font_license_is_served_next_to_the_fonts(client):
    """OFL demands the license travels with the fonts; it is served, not just
    committed, so anyone can read the terms from the app itself."""
    r = client.get("/liselott/static/fonts/LICENSE-OFL.txt")
    assert r.status_code == 200
    assert "SIL OPEN FONT LICENSE" in r.get_data(as_text=True)


def test_font_urls_resolve_under_any_prefix(tmp_path, monkeypatch):
    """The @font-face src is RELATIVE to the stylesheet, so the one mount
    mechanism carries the fonts too — a moved app never serves broken fonts."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LISELOTT_PREFIX", "/testmonly")
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    flask_app = create_app()
    flask_app.testing = True
    c = flask_app.test_client()
    assert c.get("/testmonly/static/fonts/lora-400.woff2").status_code == 200


# ── M8-hotfix-3 (MC 12451) — cache-correct static + the VERSION fallback ────
IMMUTABLE = "public, max-age=31536000, immutable"


def test_static_response_is_pinned_immutable(client):
    """Every asset URL already carries ?v=<version>, so the bytes behind one
    URL never change — immutable + version-key is the correct pairing. Left
    to Flask's 12 h default Cloudflare applies its own 4 h policy to .css and
    froze the wrong body under app.css (live 2026-11-13T17:25Z, the closed-
    window gate page at 378 B)."""
    r = client.get("/liselott/static/css/app.css")
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == IMMUTABLE


def test_a_static_miss_is_not_pinned(client):
    """The same class of bug, mirrored: Cloudflare caches 404s for
    static-looking URLs by default too, so pinning a miss would freeze the
    absence for a year. Only a served body gets the pin."""
    r = client.get("/liselott/static/ingenting.css")
    assert r.status_code == 404
    assert "immutable" not in r.headers.get("Cache-Control", "")


def test_read_version_reads_the_version_file_when_git_is_gone(tmp_path):
    """The vm106 mirror carries no .git, so prod booted on the literal "dev"
    and every deploy shipped an identical ?v= — a poisoned asset URL then
    survives the deploy that fixes it. The tree's own VERSION file is the key
    for that shape (git still first, §T4.4 order kept)."""
    (tmp_path / "VERSION").write_text("2026.11-2\n", encoding="utf-8")
    assert app_module._read_version(cwd=tmp_path) == "2026.11-2"


def test_read_version_still_prefers_the_git_sha(monkeypatch, tmp_path):
    sha = "a" * 40
    done = subprocess.CompletedProcess([], 0, stdout=sha + "\n", stderr="")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: done)
    (tmp_path / "VERSION").write_text("2026.11-2\n", encoding="utf-8")
    assert app_module._read_version(cwd=tmp_path) == sha


def test_shipped_version_file_is_a_version():
    """The prod fallback must never read as the literal "dev" — that is
    exactly what made every ?v= identical across deploys."""
    text = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"\d{4}\.\d{1,2}-\d+", text), text

