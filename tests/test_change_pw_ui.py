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
import contextlib
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMP = "Ganga-Boks-Temp-2026"     # the test's OWN passwords — never a real one
NEW = "Ganga-Boks-Nya-2026"


def free_port():
    """A port nobody else holds: bind(0) lets the OS hand out a free
    ephemeral one PER RUN. F-H2 (DA-verdict-c2): the fixed :8317 collided
    with other seats' scratch servers when the machine was shared — the
    one-off suite failure ("no /healthz on :8317 within 15 s") was born
    there. The server.py entrypoint takes the port from the env exactly
    as production does."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """302s surface as HTTPError so the test can assert Location itself —
    auto-following would hide exactly the redirect the contract names."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def open_no_redirect(opener, base, method, path, data=None, headers=None):
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers=headers or {})
    try:
        resp = opener.open(req, timeout=10)
        return resp.status, dict(resp.headers), resp.read().decode(
            "utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")


def form(**kw):
    return urlencode(kw).encode("ascii")


@contextlib.contextmanager
def running_server(tmp_path):
    """The real server.py on its OWN free port and its own scratch dir
    (F-H2's three fixes at once): the port is per-run, the child's output
    goes to a LOG FILE instead of a pipe nobody drains — a server that
    dies at startup leaves its death log in the failure message — and
    readiness is a RETRY LOOP against /healthz (a port can accept while
    uvicorn still imports: server up != first request ok) with a 60 s
    budget, the old 15 s one having measured too tight under load. No
    fixed sleep; 0.2 s is the poll interval, never the wait."""
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    log_path = tmp_path / "server.log"
    with log_path.open("wb") as log:
        env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
               "PORT": str(port), "LISELOTT_ENV": "dev",
               "LISELOTT_DATA_DIR": str(tmp_path)}
        proc = subprocess.Popen([sys.executable, "server.py"], cwd=REPO_ROOT,
                                env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.time() + 60
            while time.time() < deadline:
                if proc.poll() is not None:
                    raise AssertionError(
                        f"server died (exit {proc.returncode}):\n"
                        + log_path.read_text(errors="replace"))
                try:
                    with urllib.request.urlopen(base + "/healthz",
                                                timeout=2) as resp:
                        if resp.status == 200:
                            break
                except (urllib.error.URLError, ConnectionError, OSError):
                    pass
                time.sleep(0.2)
            else:
                raise AssertionError(
                    f"no /healthz on :{port} within 60 s:\n"
                    + log_path.read_text(errors="replace"))
            yield proc, base
        finally:
            proc.terminate()
            proc.wait(timeout=10)


def jar_opener():
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(CookieJar()), NoRedirect())


def test_owner_changes_password_through_the_rendered_pages(tmp_path):
    with running_server(tmp_path) as (_, base):
        owner = jar_opener()
        anon = jar_opener()

        # setup window: she sets the temp password through the same pages
        status, _, body = open_no_redirect(
            owner, base, "POST", "/liselott/satt-loesenord",
            data=form(loesenord=TEMP, bekrafta=TEMP))
        assert status == 302, status

        # THE NAV LEG: the link exists in the rendered HTML, logged-in only
        status, _, shelf = open_no_redirect(owner, base, "GET", "/liselott/")
        assert status == 200 and "Din hylla" in shelf
        assert '<a href="/liselott/byter-losenord">Byt lösenord</a>' in shelf
        status, _, landing = open_no_redirect(anon, base, "GET", "/liselott/")
        assert status == 200 and "Byt lösenord" not in landing

        # THE PAGE LEG: GET renders the form + the csrf token (200, not 405)
        status, _, page = open_no_redirect(owner, base,
                                           "GET", "/liselott/byter-losenord")
        assert status == 200, status
        for field in ("nuvarande", "ny", "ny_bekrafta"):
            assert f'name="{field}"' in page, field
        csrf = re.search(r'name="csrf" value="([^"]+)"', page).group(1)

        # THE ROTATION LEG: token read OUT OF THE PAGE, POSTed like a browser
        status, headers, _ = open_no_redirect(
            owner, base, "POST", "/liselott/byter-losenord",
            data=form(nuvarande=TEMP, ny=NEW, ny_bekrafta=NEW, csrf=csrf))
        assert status == 302, status
        assert headers["Location"] == "/liselott/logga-in", headers

        # old cookies die: a data route is back behind the guard
        status, headers, _ = open_no_redirect(owner, base, "GET",
                                              "/liselott/bibliotek")
        assert status == 302 and headers["Location"] == "/liselott/logga-in"

        # …and the NEW password logs in through the same jar
        status, headers, _ = open_no_redirect(
            owner, base, "POST", "/liselott/logga-in", data=form(loesenord=NEW))
        assert status == 302 and headers["Location"] == "/liselott/"
        status, _, shelf = open_no_redirect(owner, base, "GET", "/liselott/")
        assert status == 200 and "Din hylla" in shelf


def test_wrong_current_password_401s_through_the_page(tmp_path):
    with running_server(tmp_path) as (_, base):
        owner = jar_opener()
        open_no_redirect(owner, base, "POST", "/liselott/satt-loesenord",
                         data=form(loesenord=TEMP, bekrafta=TEMP))
        status, _, page = open_no_redirect(owner, base, "GET",
                                           "/liselott/byter-losenord")
        csrf = re.search(r'name="csrf" value="([^"]+)"', page).group(1)
        status, _, body = open_no_redirect(
            owner, base, "POST", "/liselott/byter-losenord",
            data=form(nuvarande="Fel-Gammalt-Losenord-1", ny=NEW,
                      ny_bekrafta=NEW, csrf=csrf))
        assert status == 401, status
        assert "Fel nuvarande lösenord." in body
