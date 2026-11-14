"""F-1 (SEC-verdict-12497) — the exact-bytes leg: HEAD+body on the REAL stack.

The gate ran its F-1 repro with a raw-socket HTTP client (exact bytes, no
client-side normalization) on uvicorn + WSGIMiddleware, and a test_client
is its own EnvironBuilder — it cannot stand in for what a relay or a non-
browser tooler actually writes on the wire. This is the suite's copy of
that instrument: the running_server harness from tests/test_change_pw_ui
(own scratch LISELOTT_DATA_DIR, own free port, /healthz readiness poll),
socket writes for the HEAD+body requests, sqlite reads for the §6.2
bucket. On the pre-fix tree these legs are RED exactly as the verdict
measured them: five wrong HEADs = five recorded attempts = her real login
429; a correct HEAD+body = 302 + session cookie.
"""
import socket
import sqlite3

from tests.test_change_pw_ui import (TEMP, form, jar_opener,
                                     open_no_redirect, running_server)


def raw_head(port, path, body):
    """One exact HEAD-with-payload-body request. Connection: close makes
    the server's close the end-of-response marker: read to EOF, parse the
    status line and whether ANY Set-Cookie came back."""
    wire = ("\r\n".join([
        f"HEAD {path} HTTP/1.1", f"Host: 127.0.0.1:{port}",
        "Content-Type: application/x-www-form-urlencoded",
        f"Content-Length: {len(body)}", "Connection: close"]) +
        "\r\n\r\n").encode("latin-1") + body
    with socket.create_connection(("127.0.0.1", port), timeout=10) as sock:
        sock.sendall(wire)
        chunks = []
        while True:
            got = sock.recv(4096)
            if not got:
                break
            chunks.append(got)
    head = b"".join(chunks).split(b"\r\n\r\n", 1)[0].decode("latin-1")
    status = int(head.split(" ", 2)[1])
    set_cookie = any(line.lower().startswith("set-cookie:")
                     for line in head.split("\r\n")[1:])
    return status, set_cookie


def test_raw_head_with_body_never_logs_in_or_counts(tmp_path):
    with running_server(tmp_path) as (_, base):
        port = int(base.rsplit(":", 1)[1])
        owner = jar_opener()
        status, _, _ = open_no_redirect(
            owner, base, "POST", "/liselott/satt-loesenord",
            data=form(loesenord=TEMP, bekrafta=TEMP))
        assert status == 302

        # verdict scenario (a) as lockout math, executed at the byte level
        codes = [raw_head(port, "/liselott/logga-in",
                          form(loesenord="_fel_losenord_"))[0]
                 for _ in range(5)]
        assert codes == [200] * 5          # the read answer, five times
        conn = sqlite3.connect(tmp_path / "liselott.db")
        n = conn.execute("SELECT COUNT(*) FROM login_attempts").fetchone()[0]
        conn.close()
        assert n == 0                      # nothing entered the §6.2 bucket
        status, _, _ = open_no_redirect(
            owner, base, "POST", "/liselott/logga-in",
            data=form(loesenord=TEMP))
        assert status == 302               # real login survives the storm

        # verdict scenario (b), login half: a correct-pw HEAD+body mints
        # no session — status 200 (the render) and NO Set-Cookie ever
        status, set_cookie = raw_head(port, "/liselott/logga-in",
                                      form(loesenord=TEMP))
        assert status == 200 and not set_cookie
