"""F-1 (SEC-verdict-12497) — HEAD never executes a state change.

The verdict's two failure scenarios, pinned as test-client legs (the
exact-bytes twin of the lockout math lives in tests/test_raw_head_body.py
against the real uvicorn + WSGIMiddleware stack, as the gate ran it):

* (a) the browser-weaponizable lockout: five wrong-password HEADs at
  /logga-in must record ZERO login_attempts. The old "GET renders /
  everything else processes" split made every HEAD a failed POST inside
  the §6.2 bucket — five of them and the owner's NEXT real login is 429
  for 15 min (the limit is checked BEFORE password verification, so even
  her correct password is refused).
* (b) HEAD+body carrying a cookie: neither login nor the password change
  may execute on a HEAD — POST is the ONLY processing method on the three
  dual-method views; every other method gets the route's read answer.
* the CSRF machinery no longer looks away from HEAD: the ORIGIN rule now
  checks HEAD exactly as it checks POST (verdict scenario (a) is a
  cross-origin fetch, and browsers always attach Origin to one). The
  TOKEN rule stays a state-change rule — HEAD is READ_METHODS to the
  guard and processes nothing after this wave, and token-checking HEAD
  would 400 the anonymous public reads MC 12497 just made public.
"""
import sqlite3

import pytest

from app import create_app

PASSWORD = "_test_losenord_"
NEW = "Ganga-Boks-Nya-2026"


@pytest.fixture()
def configured(tmp_path, monkeypatch):
    """Configured scratch state; the fixture's own client is LOGGED IN
    (setting the password establishes the session, §6.1)."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    app = create_app()
    app.testing = True
    client = app.test_client()
    assert client.post("/liselott/satt-loesenord",
                       data={"loesenord": PASSWORD,
                             "bekrafta": PASSWORD}).status_code == 302
    return tmp_path, client


def pw_hash(tmp_path):
    conn = sqlite3.connect(tmp_path / "liselott.db")
    row = conn.execute("SELECT value FROM settings WHERE key = 'password_hash'"
                       ).fetchone()
    conn.close()
    return row[0] if row else None


def attempts(tmp_path):
    conn = sqlite3.connect(tmp_path / "liselott.db")
    n = conn.execute("SELECT COUNT(*) FROM login_attempts").fetchone()[0]
    conn.close()
    return n


def test_head_with_body_never_logs_in(configured):
    _, _ = configured
    anon = create_app().test_client()
    r = anon.head("/liselott/logga-in", data=f"loesenord={PASSWORD}",
                  content_type="application/x-www-form-urlencoded")
    assert r.status_code == 200                 # the form renders, like GET
    assert "Set-Cookie" not in r.headers         # no session minted by a HEAD
    r = anon.get("/liselott/onska")              # …and she is still anonymous
    assert r.status_code == 302


def test_head_rejections_never_fill_the_lockout_bucket(configured):
    """Lockout math, executed: 5 recorded rejections drain the owner (§6.2).
    Five wrong HEADs leave the bucket EMPTY, so her sixth request — the
    real POST with the real password — logs in (302), never 429."""
    tmp, _ = configured
    anon = create_app().test_client()
    for _ in range(5):
        r = anon.head("/liselott/logga-in", data="loesenord=_fel_losenord_",
                      content_type="application/x-www-form-urlencoded")
        assert r.status_code == 200
    assert attempts(tmp) == 0
    r = anon.post("/liselott/logga-in", data={"loesenord": PASSWORD})
    assert r.status_code == 302
    assert r.headers["Location"] == "/liselott/"


def test_head_never_changes_the_password(configured):
    """Verdict scenario (b): owner cookie + HEAD+body, no token, unchecked
    Origin — pre-fix this MOVED the password hash (a CSRF defence bypass at
    full owner privilege)."""
    tmp, owner = configured
    before = pw_hash(tmp)
    r = owner.head("/liselott/byter-losenord",
                   data=f"nuvarande={PASSWORD}&ny={NEW}&ny_bekrafta={NEW}",
                   content_type="application/x-www-form-urlencoded")
    assert r.status_code == 200                  # the form renders, like GET
    assert pw_hash(tmp) == before                # nothing moved
    fresh = create_app().test_client()           # the new password is NOT live
    assert fresh.post("/liselott/logga-in",
                      data={"loesenord": NEW}).status_code == 401


def test_cross_site_head_hits_the_origin_rule(configured):
    """HEAD is no longer invisible to _csrf_gate: the Origin rule (the one
    POST has always had) 400s a cross-site HEAD on an allow-listed door and
    on a public page alike. A HEAD answer is header-only by definition —
    the status is the whole assertion (the csrf-fel COPY is pinned on the
    POST legs in tests/test_csrf.py)."""
    _, _ = configured
    anon = create_app().test_client()
    for path in ("/liselott/logga-in", "/liselott/bibliotek"):
        r = anon.head(path, headers={"Origin": "https://evil.example"})
        assert r.status_code == 400, path


def test_head_stays_a_read_on_the_public_set(configured):
    """The flip's floor: closing the CSRF skip must not cost HEAD its read
    answer — a same-shape (Originless) HEAD is exactly the anonymous read
    MC 12497 promised, with no cookie and never a CSRF page."""
    _, _ = configured
    anon = create_app().test_client()
    for path in ("/liselott/", "/liselott/bibliotek", "/liselott/healthz"):
        r = anon.head(path)
        assert r.status_code == 200, path
        assert "Set-Cookie" not in r.headers, path


def test_head_never_sets_the_first_password(tmp_path, monkeypatch):
    """The fresh-state door: HEAD+body against /satt-loesenord must leave
    the password UNSET (pre-fix it set it, anonymous, in the setup window —
    the verdict's `password set via HEAD? (1,)`)."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    anon = create_app().test_client()
    r = anon.head("/liselott/satt-loesenord",
                  data=f"loesenord={PASSWORD}&bekrafta={PASSWORD}",
                  content_type="application/x-www-form-urlencoded")
    assert r.status_code == 200
    assert pw_hash(tmp_path) is None
    # the door is still open for her real POST
    assert anon.post("/liselott/satt-loesenord",
                     data={"loesenord": PASSWORD,
                           "bekrafta": PASSWORD}).status_code == 302
