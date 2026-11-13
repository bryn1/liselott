"""OQ-2 (owner ruling 2026-11-12) — the admin "hitta omslag" helper: the admin
pastes a PAGE url, the app fetches that page server-side and pulls the cover
out of it (`og:image`, or the largest `<img>` as fallback), storing it with
cover_source='manual-url'. Shipped here (server side + util + tests); the UI
wiring lands in S5.

Route posture is inherited, not reinvented (§6.4/§6.6): the path is guarded by
the existing login gate and the POST needs the session CSRF token — it is NOT
in TOKENLESS_POSTS, asserted below. No new gate mechanism.

Bounds from the ruling, each one tested: http/https only (refused BEFORE any
fetch — measured: the raw urllib opener happily reads file:///etc/hostname, so
the guard is load-bearing, not decoration), a 900 000-byte cap on the response
body, an image-type allowlist by magic bytes, a timeout, and never following a
redirect into file:// or a gopher-like scheme — the last leg runs a REAL local
loopback server that answers 302 -> file:///etc/hostname, offline-safe and the
only way to prove it end to end."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from PIL import Image

from app import create_app, db, enrich, omslag

ROOT = Path(__file__).resolve().parent.parent
COVER_FIXTURE = ROOT / "tests" / "fixtures" / "cover_sample.jpg"

PAGE_WITH_OG = """<!doctype html><html><head>
<meta property="og:image" content="/bilder/omslag.jpg">
<meta property="og:title" content="Stöld">
</head><body><img src="/litet.png" width="40" height="60">
<img src="/stort.png" width="900" height="1200"></body></html>"""

PAGE_WITHOUT_OG = """<!doctype html><html><body>
<img src="/pyttel.png" width="40" height="60">
<img src="/mellan.png" width="300" height="400">
<img src="/storst.png" width="1200" height="800"></body></html>"""


@pytest.fixture()
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    conn = db.connect()
    db.init_db(conn)
    conn.execute("INSERT INTO book (id, title, book_key, format, read_year, status,"
                 " created, updated) VALUES (1,'Stöld','stold','bok',2022,'read',"
                 "'2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')")
    conn.commit()
    yield conn, tmp_path
    conn.close()


class FakeFetch:
    """A transport that records what was asked — so 'refused before any fetch'
    is an assertion about a call that never happened, not about a string."""

    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def __call__(self, url, **kw):
        self.calls.append(url)
        body = self.pages[url]
        if isinstance(body, Exception):
            raise body
        return body


def page_fetch(url="https://bokhandel.example/stold"):
    return FakeFetch({url: PAGE_WITH_OG.encode(),
                      "https://bokhandel.example/bilder/omslag.jpg": COVER_FIXTURE.read_bytes()})


# ---- the extraction util ----------------------------------------------------

def test_og_image_wins_and_is_resolved_against_the_page():
    got = omslag.extract_cover_url(PAGE_WITH_OG, "https://bokhandel.example/stold")
    assert got == "https://bokhandel.example/bilder/omslag.jpg"


def test_without_og_image_the_largest_img_wins():
    got = omslag.extract_cover_url(PAGE_WITHOUT_OG, "https://x.test/a")
    assert got == "https://x.test/storst.png"


def test_a_page_with_no_image_yields_nothing():
    assert omslag.extract_cover_url("<html><body>tomt</body></html>", "https://x.test/") is None


def test_a_data_uri_is_never_a_cover_source():
    """A data: URI in a page is content, never something the app fetches back."""
    html = '<html><head><meta property="og:image" content="data:image/png;base64,AAAA">'
    assert omslag.extract_cover_url(html, "https://x.test/") is None


# ---- the fetcher's bounds ---------------------------------------------------

def test_fetcher_stores_the_found_cover_as_manual_url(state):
    conn, tmp = state
    fetch = page_fetch()
    outcome = omslag.hamta_omslag(conn, 1, "https://bokhandel.example/stold", get=fetch)
    assert outcome["ok"] is True and outcome["cover_source"] == "manual-url"
    row = conn.execute("SELECT cover_path, cover_source FROM book").fetchone()
    assert row == ("covers/1.jpg", "manual-url")          # schema CHECK accepts it
    with Image.open(tmp / "covers" / "1.jpg") as img:
        assert img.format == "JPEG" and img.size[0] <= 340 and img.size[1] <= 510
    assert fetch.calls == ["https://bokhandel.example/stold",
                           "https://bokhandel.example/bilder/omslag.jpg"]


def test_non_http_page_url_is_refused_before_any_fetch(state):
    """VERIFIED load-bearing: enrich.http_get("file:///etc/hostname") really
    does read the file, so this refusal is the only thing between a pasted url
    and the local disk."""
    conn, tmp = state
    for bad in ("file:///etc/passwd", "gopher://x.test/", "javascript:alert(1)",
                "ftp://x.test/a", "/relative/bara"):
        fetch = FakeFetch({})
        outcome = omslag.hamta_omslag(conn, 1, bad, get=fetch)
        assert outcome["ok"] is False, bad
        assert fetch.calls == [], f"{bad} nådde transporten"
    assert conn.execute("SELECT cover_path FROM book").fetchone()[0] is None


def test_oversize_page_body_is_refused(state):
    conn, tmp = state
    fat = FakeFetch({"https://x.test/a": b"<html>" + b"x" * (enrich.MAX_BODY + 1)})
    outcome = omslag.hamta_omslag(conn, 1, "https://x.test/a", get=fat)
    assert outcome["ok"] is False and "900" in outcome["fel"]
    assert not (tmp / "covers").exists()                   # nothing half-written
    assert conn.execute("SELECT cover_path FROM book").fetchone()[0] is None


def test_oversize_image_body_is_refused(state):
    conn, tmp = state
    fat = FakeFetch({"https://x.test/a": PAGE_WITH_OG.encode(),
                     "https://x.test/bilder/omslag.jpg": b"\xff\xd8\xff" + b"y" * (enrich.MAX_BODY + 1)})
    outcome = omslag.hamta_omslag(conn, 1, "https://x.test/a", get=fat)
    assert outcome["ok"] is False and "900" in outcome["fel"]
    assert not (tmp / "covers").exists()


def test_non_image_bytes_are_refused(state):
    """An og:image that points at HTML/a WAF screen is refused by magic bytes,
    not stored, and the row keeps its old cover."""
    conn, tmp = state
    fetch = FakeFetch({"https://x.test/a": PAGE_WITH_OG.encode(),
                       "https://x.test/bilder/omslag.jpg": b"<html>404 hittas ej</html>"})
    outcome = omslag.hamta_omslag(conn, 1, "https://x.test/a", get=fetch)
    assert outcome["ok"] is False and "bild" in outcome["fel"]
    assert conn.execute("SELECT cover_path FROM book").fetchone()[0] is None


def test_a_page_that_fails_to_fetch_reports_it_without_crashing(state):
    conn, tmp = state
    fetch = FakeFetch({"https://x.test/a": enrich.ProviderUnavailable("transport failed")})
    outcome = omslag.hamta_omslag(conn, 1, "https://x.test/a", get=fetch)
    assert outcome == {"ok": False, "fel": outcome["fel"]}
    assert " kunde inte hämtas" in outcome["fel"]


# ---- the redirect rule, proven against a real loopback server --------------

class _Redirect(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(302)
        self.send_header("Location", "file:///etc/hostname")
        self.end_headers()

    def log_message(self, *a):
        pass


def test_a_redirect_into_a_local_file_scheme_is_never_followed():
    """Real socket, offline-safe: the server (127.0.0.1 only) 302s to
    file:///etc/hostname. Following it would read the host's file — the fetcher
    must fail closed instead."""
    srv = HTTPServer(("127.0.0.1", 0), _Redirect)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    try:
        with pytest.raises(enrich.ProviderUnavailable):
            enrich.http_get(f"http://127.0.0.1:{port}/vidare", attempts=1)
    finally:
        srv.shutdown()


# ---- the route: the existing guard + CSRF, no new mechanism -----------------

PASSWORD = "_test_losenord_"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    app = create_app()
    app.testing = True
    c = app.test_client()
    assert c.post("/liselott/satt-loesenord",
                  data={"loesenord": PASSWORD, "bekrafta": PASSWORD}).status_code == 302
    return app, c, tmp_path


def test_the_route_is_post_only_csrf_protected_and_guarded(client):
    from app import auth
    app, c, tmp = client
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert "/omslag/<int:book_id>/hitta" in rules
    assert "/omslag/<int:book_id>/hitta" not in auth.TOKENLESS_POSTS
    assert "/omslag/<int:book_id>/hitta" not in auth.UNAUTHENTICATED_ALLOW
    # anonymous (a client with no session cookie at all): the guard redirects,
    # the view never runs
    anon = app.test_client()
    assert anon.post("/liselott/omslag/1/hitta",
                     data={"sida_url": "https://x.test/a"}).status_code == 302
    # authenticated (satt-loesenord logs the admin in) but WITHOUT the session
    # csrf token: the §6.6 gate answers 400, the view still never runs
    r = c.post("/liselott/omslag/1/hitta", data={"sida_url": "https://x.test/a"})
    assert r.status_code == 400 and "säkerhetsmärket" in r.text.casefold()  # §6.6, §9 copy


def test_the_route_stores_the_cover_and_says_so(client, monkeypatch):
    app, c, tmp = client
    conn = db.connect()
    db.init_db(conn)
    conn.execute("INSERT INTO book (id, title, book_key, format, read_year, status,"
                 " created, updated) VALUES (1,'Stöld','stold','bok',2022,'read',"
                 "'2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(omslag, "http_get", page_fetch())
    c.post("/liselott/logga-in", data={"loesenord": PASSWORD})
    with c.session_transaction("/liselott/logga-in") as sess:   # cookie is path-scoped
        token = sess["csrf"]
    r = c.post("/liselott/omslag/1/hitta",
               data={"sida_url": "https://bokhandel.example/stold", "csrf": token})
    assert r.status_code == 200
    assert r.get_json() == {"ok": True, "cover_source": "manual-url", "book_id": 1}
    assert (tmp / "covers" / "1.jpg").exists()


def test_the_route_reports_a_refusal_as_a_swedish_message_not_a_500(client, monkeypatch):
    app, c, tmp = client
    conn = db.connect()
    db.init_db(conn)
    conn.execute("INSERT INTO book (id, title, book_key, format, read_year, status,"
                 " created, updated) VALUES (1,'Stöld','stold','bok',2022,'read',"
                 "'2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(omslag, "http_get", FakeFetch({}))
    c.post("/liselott/logga-in", data={"loesenord": PASSWORD})
    with c.session_transaction("/liselott/logga-in") as sess:   # cookie is path-scoped
        token = sess["csrf"]
    r = c.post("/liselott/omslag/1/hitta", data={"sida_url": "file:///etc/passwd",
                                                 "csrf": token})
    assert r.status_code == 400
    assert r.get_json()["ok"] is False
    assert "http" in r.get_json()["fel"]                   # Swedish, names the rule
    assert not (tmp / "covers" / "1.jpg").exists()


def test_manual_url_is_a_legal_cover_source_on_both_tables(state):
    """The CHECK on book AND candidate had to learn the new source, or the
    owner's ruling would die on a constraint."""
    conn, tmp = state
    conn.execute("UPDATE book SET cover_source = 'manual-url' WHERE id = 1")
    conn.execute("INSERT INTO candidate (title, author_name, cover_source, fetched_at)"
                 " VALUES ('Nästa bok','Vem Som Helst','manual-url',"
                 "'2026-01-01T00:00:00Z')")
    conn.commit()
    assert conn.execute("SELECT cover_source FROM book").fetchone()[0] == "manual-url"
    assert conn.execute("SELECT cover_source FROM candidate").fetchone()[0] == "manual-url"
    with pytest.raises(db.sqlite3.IntegrityError):
        conn.execute("UPDATE book SET cover_source = 'hax' WHERE id = 1")
