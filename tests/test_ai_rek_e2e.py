"""MC 12617 (M11-N8b, DA c7 F-P4-10) — the PERMANENT E2E legs the c7 probe
proved and the suite lacked: the runner MODULE (real curl through
_curl_config) against the REAL app (create_app + werkzeug make_server on a
REAL socket, the real door auth `hmac.compare_digest` over
`request.headers`), DB effect read back. The stub-listener wire legs
(tests/test_door_transport.py) and the test_client door legs each held
half the chain; these legs hold the COMPOSITION: the config header
survives real HTTP transport AND the real door accepts it — and a wrong
token lands NOTHING (auth really ran). Shape adopted from the DA c7
template (out/.tmp/da-c7/probe4_e2e_c7.py); the probe's pris half died
with the price/sale feature (MC 12606) — the ai-rek door is THE machine
door standing. make_server in-thread needs nothing beyond the pinned
requirements (no uvicorn, no subprocess).
"""
import sqlite3
import threading

import pytest
from werkzeug.serving import make_server

from app import auth, create_app
from scripts import ai_rek_pass as rp
from tests.test_ai_rek_pass import (GRADERADE, FakeLane, isbn, korpus_tsv,
                                    library_med_html, shelf_html, svar_alla)
from tests.test_browse import seed_shelf

TOKEN = "ab" * 32                       # 64 hex, the door's own shape


@pytest.fixture()
def app_på_socket(tmp_path, monkeypatch):
    """The REAL app on a REAL socket (port 0 — never a fixed port under
    parallel runs): configured site (is_configured gate), the browse
    fixture shelf through the real schema, ai-rek door armed by env."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    monkeypatch.setenv(rp.ENV_TOKEN, TOKEN)
    db = str(tmp_path / "liselott.db")
    seed_shelf(db)
    with sqlite3.connect(db) as conn:
        auth.set_setting(conn, "password_hash",
                         auth.hash_password("e2e-losen-12345"))
    srv = make_server("127.0.0.1", 0, create_app(), threaded=True)
    tråd = threading.Thread(target=srv.serve_forever, daemon=True)
    tråd.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}", db
    finally:
        srv.shutdown()
        tråd.join(timeout=5)


def rek_rader(n=2):
    """Synthetic isbns only — the 9999 lane from tests/test_ai_rek_pass.py
    is NO valid ISBN group and carries ZERO hits in the private real-ISBN
    list (MC 12616's exposure lesson, applied pre-emptively here)."""
    return [{"title": f"E2E-Rek {k}", "author_name": "E2 Eer", "year": 2026,
             "isbn13": isbn(100 + k), "reason": "suite-leg",
             "source": "https://rec.example/e2e", "fit": 0.9 - k / 100,
             "kategori": ("nyhet" if k % 2 else "klassiker")}
            for k in range(n)]


def test_e2e_full_swap_lands_rows_through_the_real_door(app_på_socket):
    """rp.door_post(full=True) — real curl, real config-header transport,
    real HTTP, real door — 200 with deleted_n in the receipt, and the
    rows read back from the DB in the door's own state machine ('new').
    This is the composition the DA c7 probe measured; here it is law."""
    base, db = app_på_socket
    status, kvittens = rp.door_post(f"{base}/liselott/ai-rek", TOKEN,
                                    rek_rader(), full=True)
    assert status == 200, kvittens
    assert b"deleted_n" in kvittens          # the sweep receipt shape
    with sqlite3.connect(db) as conn:
        landat = conn.execute("SELECT title, kategori, state FROM ai_rek"
                              " ORDER BY title").fetchall()
    assert landat == [("E2E-Rek 0", "klassiker", "new"),
                      ("E2E-Rek 1", "nyhet", "new")]


def test_e2e_wrong_token_lands_nothing(app_på_socket):
    """The negative control the composition NEEDS: a well-shaped WRONG
    token is uniformly 401 and the table stays empty — the door auth
    really executed on the real socket, the header was not ignored."""
    base, db = app_på_socket
    status, _ = rp.door_post(f"{base}/liselott/ai-rek", "be" * 32,
                             rek_rader(), full=True)
    assert status == 401
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM ai_rek").fetchone()[0] == 0


def test_e2e_whole_run_pass_delivers_over_a_real_socket(tmp_path,
                                                        app_på_socket,
                                                        monkeypatch):
    """THE leg: run_pass with its library/lane seams faked but the POST
    seam at its DEFAULT (the real door_post) — the whole chain, corpus
    file through the join, gates, transport, HTTP, door, DB. 21 fixture
    rows ride, exit 0, and 21 rows read back. Nothing on this page mocks
    curl any more than the MC 12616 wire legs demanded."""
    base, db = app_på_socket
    monkeypatch.setenv(rp.ENV_TOKEN, TOKEN)
    monkeypatch.setenv("AI_REK_REHEARSAL_DIR", str(tmp_path))
    ts = korpus_tsv(tmp_path / "corpus.tsv")
    code = rp.run_pass(ts, f"{base}/liselott/bibliotek", f"{base}/liselott",
                       get_library=library_med_html(shelf_html(GRADERADE)),
                       lane=FakeLane(svar_alla(21)), say=lambda line: None)
    assert code == 0
    with sqlite3.connect(db) as conn:
        n, kat = conn.execute("SELECT COUNT(*),"
                              " COUNT(DISTINCT kategori) FROM ai_rek"
                              " WHERE state = 'new'").fetchone()
    assert n == 21 and kat == 3              # all rows, all three categories
