"""T2.4 — login rate limit (5 fails / 15 min -> 429, §6.2, P2-1): the bucket
key is CF-Connecting-IP when present, else the LAST X-Forwarded-For hop (the
renderer appends the real peer — the FIRST hop is client-supplied garbage),
else REMOTE_ADDR. Rows older than 1 h are pruned on every check. /satt-loesenord
POST shares the same bucket (§6.1)."""
import sqlite3

from datetime import datetime, timedelta, timezone

import pytest

from app import create_app

PASSWORD = "_test_losenord_"
WRONG = {"loesenord": "_fel_losenord_"}


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    app = create_app()
    app.testing = True
    client = app.test_client()
    r = client.post("/liselott/satt-loesenord",
                    data={"loesenord": PASSWORD, "bekrafta": PASSWORD})
    assert r.status_code == 302
    return app, client, tmp_path


def fail_times(client, n, headers=None):
    codes = [client.post("/liselott/logga-in", data=WRONG,
                         headers=headers or {}).status_code for _ in range(n)]
    return codes


def test_five_fails_sixth_429(env):
    _, client, _ = env
    codes = fail_times(client, 5)
    assert codes == [401] * 5
    r = client.post("/liselott/logga-in", data=WRONG)
    assert r.status_code == 429
    assert "För många försök" in r.text


def test_correct_password_inside_window_still_429(env):
    _, client, _ = env
    fail_times(client, 5)
    r = client.post("/liselott/logga-in", data={"loesenord": PASSWORD})
    assert r.status_code == 429  # limit checked BEFORE password verification


def test_restart_same_db_still_429(env):
    app, client, tmp_path = env
    fail_times(client, 5)
    app2 = create_app()  # "restart": new process, same DB
    app2.testing = True
    r = app2.test_client().post("/liselott/logga-in", data=WRONG)
    assert r.status_code == 429


def test_cf_connecting_ip_is_the_bucket(env):
    """Spoof leg: X-Forwarded-For rotates every request, CF-Connecting-IP
    constant -> 429 anyway (first-hop garbage never binds, P2-1)."""
    _, client, _ = env
    codes = [client.post("/liselott/logga-in", data=WRONG, headers={
        "CF-Connecting-IP": "9.9.9.9",
        "X-Forwarded-For": f"10.20.{i}.1, 5.6.7.8",
    }).status_code for i in range(5)]
    assert codes == [401] * 5
    r = client.post("/liselott/logga-in", data=WRONG, headers={
        "CF-Connecting-IP": "9.9.9.9", "X-Forwarded-For": "10.99.99.9, 5.6.7.8"})
    assert r.status_code == 429


def test_last_xff_hop_is_bucket_without_cf(env):
    """No CF-Connecting-IP (not behind Cloudflare): the LAST XFF hop — the one
    the trusted nginx appends — is the bucket key."""
    _, client, _ = env
    codes = [client.post("/liselott/logga-in", data=WRONG, headers={
        "X-Forwarded-For": f"203.0.113.{i}, 198.51.100.7",
    }).status_code for i in range(5)]
    assert codes == [401] * 5
    r = client.post("/liselott/logga-in", data=WRONG, headers={
        "X-Forwarded-For": "203.0.113.99, 198.51.100.7"})
    assert r.status_code == 429


def test_aged_rows_pruned_not_counted(env, tmp_path):
    _, client, tmp_path = env
    old = iso(datetime.now(timezone.utc) - timedelta(hours=2))
    conn = sqlite3.connect(tmp_path / "liselott.db")
    conn.executemany("INSERT INTO login_attempts (ip, ts) VALUES (?, ?)",
                     [("127.0.0.1", old)] * 6)
    conn.commit()
    conn.close()
    r = client.post("/liselott/logga-in", data=WRONG)
    assert r.status_code == 401  # 6 aged rows are NOT 6 failures
    conn = sqlite3.connect(tmp_path / "liselott.db")
    cutoff = iso(datetime.now(timezone.utc) - timedelta(hours=1))
    n_old = conn.execute("SELECT COUNT(*) FROM login_attempts WHERE ts < ?",
                        (cutoff,)).fetchone()[0]
    conn.close()
    assert n_old == 0  # pruned on the check (§6.2)


def test_setup_post_shares_the_bucket(tmp_path, monkeypatch):
    """§6.1: /satt-loesenord POST shares the login_attempts bucket keyed by
    client_ip — the window bounds exposure further; the limit still applies."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    app = create_app()
    app.testing = True
    client = app.test_client()
    bad = {"loesenord": "kort", "bekrafta": "kort"}
    codes = [client.post("/liselott/satt-loesenord", data=bad).status_code
             for _ in range(5)]
    assert codes == [400] * 5
    r = client.post("/liselott/satt-loesenord",
                    data={"loesenord": PASSWORD, "bekrafta": PASSWORD})
    assert r.status_code == 429  # bucket shared even though this POST was
    # never a password failure — validation rejections count too
