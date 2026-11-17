"""MC 12601 (M11-N5R) — the ONE curl-subprocess transport the fleet-side
runners ride. MC 12570's `_curl` moved VERBATIM out of scripts/pris_vakt.py
(the measured CF fact that made it: Cloudflare 403s python-urllib on
sibbamala.com, curl passes the edge), so ai_rek_pass (the /ai-rek runner)
and pris_vakt (the /pris runner) share ONE transport instead of forking a
second one — one mechanism, two callers. The body is byte-identical to the
MC 12570 original; the patch surface moved with it (tests monkeypatch
`curl_transport.subprocess.run`).

MC 12616 (DA c3 P2) adds `_curl_config` beside `_curl`: header delivery
whose SECRET bytes never reach argv (the reproduced /proc/<curl>/cmdline
leak). `_curl`'s signature is UNCHANGED — it stays the plain path the
GETs ride. MC 12616 c5 (DA F-P2-1): the first wave's "pris keeps the
header-as-argv path" reading was VOID — the card append and LEDGER:1079
charge BOTH callers and no ruling ever pinned pris — so BOTH door
runners now ride `_curl_config`, byte-identical ON THE WIRE (same header
name, same value): one secret delivery, not two.
"""
import os
import re
import subprocess
import tempfile

CURL = "curl"                               # the production transport (MC 12570)
WATCHDOG_GRACE_S = 5                        # hard subprocess stop, wedged curl
_HOKNAVN = re.compile(r"[A-Za-z0-9:-]+")    # the config guard's name shape
#                                         (MC 12616 c5, DA F-P3-1) — the
#                                         shape BOTH door headers carry


def _curl(args, *, timeout_s, stdin_data=b""):
    """MC 12570 — the transport BOTH plain legs ride since 2026-11-16: curl
    via subprocess, argv list, never a shell, curl's DEFAULT UA. The named
    urllib era is over: the first manual tick 2026-11-16 06:19 measured the
    fleet's known CF fact — Cloudflare 403s python-urllib ("bibliotek 403"),
    curl passes the edge. The status is captured with --write-out, the body
    lands in a temp file; (0, b"") is a transport failure, never a zero
    result, and --max-time + the subprocess timeout (grace on top) is the
    hard ceiling — a wedged curl dies, the tick never rides into the kill."""
    with tempfile.NamedTemporaryFile() as body_file:
        argv = [CURL, "--silent", "--show-error",
                "--max-time", str(timeout_s),
                "--write-out", "%{http_code}",
                "--output", body_file.name, *args]
        try:
            proc = subprocess.run(argv, input=stdin_data,
                                  capture_output=True,
                                  timeout=timeout_s + WATCHDOG_GRACE_S)
        except (OSError, subprocess.SubprocessError):
            return 0, b""
        body_file.seek(0)
        body = body_file.read()
    if proc.returncode != 0:
        return 0, b""                      # connect/timeout exit classes
    try:
        return int(proc.stdout), body
    except ValueError:
        return 0, b""                      # no parseable status: no answer


def _curl_config(secret_headers, build_args, *, timeout_s, stdin_data=b""):
    """MC 12616 (DA c3 P2, the reproduced /proc/<curl>/cmdline leak) — the
    delivery that keeps SECRET header bytes OUT of the child's argv: the
    named headers are written to a per-call tmpfile (tempfile.mkstemp —
    created 0600), curl reads them via `--config @<path>`, and the file is
    unlinked in the finally. The content is never echoed or logged: this
    function never prints, and `_curl`'s failure path answers (0, b"").
    THE GUARD (MC 12616 c5, DA F-P3-1 — curl expands BACKSLASH escapes
    inside the quoted value, measured as a genuine wire-newline injection
    from a literal backslash-n): EVERY pair is validated BEFORE any file
    exists — name full-matching [A-Za-z0-9:-]+, value free of `"`,
    backslash and any non-printable ASCII — so a token value can never
    inject config lines, and a rejected multi-header call writes nothing
    at all (the DA's F-P4-3 wording face). `build_args(config_arg)`
    returns the caller's curl argv tail with the "@"-prefixed reference
    where it belongs; the argv that reaches /proc then carries ZERO
    secret bytes (legs: the live-curl-cmdline pair in
    tests/test_door_transport.py, both doors)."""
    for namn, varde in secret_headers:                # EVERY pair, BEFORE
        if not _HOKNAVN.fullmatch(namn):              # a single byte of
            raise ValueError("confighögardet ur formen — vägrar skriva")
        if any(c in varde for c in '"\\\r\n') or not varde.isprintable():
            raise ValueError("configvärdet ur formen — vägrar skriva")
    fd, path = tempfile.mkstemp(prefix="curl-hdr-")
    try:
        with os.fdopen(fd, "w", encoding="ascii") as fh:
            for namn, varde in secret_headers:
                fh.write(f'header = "{namn}: {varde}"\n')
        return _curl(build_args("@" + path), timeout_s=timeout_s,
                     stdin_data=stdin_data)
    finally:
        try:
            os.unlink(path)
        except OSError:                              # DA c5 F-P4-2 (a real
            try:                                     # 0600 leftover was
                os.unlink(path)                      # witnessed): best-effort
            except OSError:                          # SECOND unlink, then
                pass                                 # stated residue — the
                                                     # file is one header
                                                     # line, 0600, uid-owned
