"""F-C / P1-1 — the "Byt lösenord" door THROUGH THE REAL UI (MC 12451).

T2.7's gate passed on a POST built by hand with the token pulled via
session_transaction — the shipped consequence: the template existed but no
GET route and no nav link reached it, and the owner could not change her
password at all (DA-verdict P1-1, TEST-verdict F-C: GET 405). This file is
the leg that shortcut skipped: the REAL server.py (subprocess, own scratch
LISELOTT_DATA_DIR, own test passwords), a cookie jar, and nothing but
rendered HTML in and form posts out.

Legs: the nav link is IN the rendered page's HTML (logged-in only — the
anonymous landing never carries it); GET /liselott/byter-losenord -> 200
with current+new+confirm fields and the csrf token riding the render; the
POST (token read OUT OF THE PAGE, never out of the session) rotates: 302 to
/logga-in, the OLD cookie is dead on a data route, and the NEW password
logs in again through the same jar.
"""
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parent.parent
PORT = 8317
BASE = f"http://127.0.0.1:{PORT}"
TEMP = "Ganga-Boks-Temp-2026"     # the test's OWN passwords — never a real one
NEW = "Ganga-Boks-Nya-2026"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """302s surface as HTTPError so the test can assert Location itself —
    auto-following would hide exactly the redirect the contract names."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_no_redirect(opener, method, path, data=None, headers=None):
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers=headers or {})
    try:
        resp = opener.open(req, timeout=10)
        return resp.status, dict(resp.headers), resp.read().decode(
            "utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")


def form(**kw):
    return urlencode(kw).encode("ascii")


def server(tmp_path):
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
           "PORT": str(PORT), "LISELOTT_ENV": "dev",
           "LISELOTT_DATA_DIR": str(tmp_path)}
    proc = subprocess.Popen([sys.executable, "server.py"], cwd=REPO_ROOT,
                            env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    try:
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(BASE + "/healthz",
                                            timeout=1) as resp:
                    assert resp.status == 200
                    return proc
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                if proc.poll() is not None:
                    raise AssertionError(
                        "server died:\n" + proc.stdout.read().decode(
                            errors="replace"))
                time.sleep(0.2)
        raise AssertionError(f"no /healthz on :{PORT} within 15 s")
    except BaseException:
        proc.terminate()
        raise


def jar_opener():
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(CookieJar()), NoRedirect())


def test_owner_changes_password_through_the_rendered_pages(tmp_path):
    proc = server(tmp_path)
    try:
        owner = jar_opener()
        anon = jar_opener()

        # setup window: she sets the temp password through the same pages
        status, _, body = open_no_redirect(
            owner, "POST", "/liselott/satt-loesenord",
            data=form(loesenord=TEMP, bekrafta=TEMP))
        assert status == 302, status

        # THE NAV LEG: the link exists in the rendered HTML, logged-in only
        status, _, shelf = open_no_redirect(owner, "GET", "/liselott/")
        assert status == 200 and "Din hylla" in shelf
        assert '<a href="/liselott/byter-losenord">Byt lösenord</a>' in shelf
        status, _, landing = open_no_redirect(anon, "GET", "/liselott/")
        assert status == 200 and "Byt lösenord" not in landing

        # THE PAGE LEG: GET renders the form + the csrf token (200, not 405)
        status, _, page = open_no_redirect(owner, "GET",
                                           "/liselott/byter-losenord")
        assert status == 200, status
        for field in ("nuvarande", "ny", "ny_bekrafta"):
            assert f'name="{field}"' in page, field
        csrf = re.search(r'name="csrf" value="([^"]+)"', page).group(1)

        # THE ROTATION LEG: token read OUT OF THE PAGE, POSTed like a browser
        status, headers, _ = open_no_redirect(
            owner, "POST", "/liselott/byter-losenord",
            data=form(nuvarande=TEMP, ny=NEW, ny_bekrafta=NEW, csrf=csrf))
        assert status == 302, status
        assert headers["Location"] == "/liselott/logga-in", headers

        # old cookies die: a data route is back behind the guard
        status, headers, _ = open_no_redirect(owner, "GET",
                                              "/liselott/bibliotek")
        assert status == 302 and headers["Location"] == "/liselott/logga-in"

        # …and the NEW password logs in through the same jar
        status, headers, _ = open_no_redirect(
            owner, "POST", "/liselott/logga-in", data=form(loesenord=NEW))
        assert status == 302 and headers["Location"] == "/liselott/"
        status, _, shelf = open_no_redirect(owner, "GET", "/liselott/")
        assert status == 200 and "Din hylla" in shelf
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_wrong_current_password_401s_through_the_page(tmp_path):
    proc = server(tmp_path)
    try:
        owner = jar_opener()
        open_no_redirect(owner, "POST", "/liselott/satt-loesenord",
                         data=form(loesenord=TEMP, bekrafta=TEMP))
        status, _, page = open_no_redirect(owner, "GET",
                                           "/liselott/byter-losenord")
        csrf = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
        status, _, body = open_no_redirect(
            owner, "POST", "/liselott/byter-losenord",
            data=form(nuvarande="Fel-Gammalt-Losenord-1", ny=NEW,
                      ny_bekrafta=NEW, csrf=csrf))
        assert status == 401, status
        assert "Fel nuvarande lösenord." in body
    finally:
        proc.terminate()
        proc.wait(timeout=10)
