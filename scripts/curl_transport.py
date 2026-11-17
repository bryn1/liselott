"""MC 12601 (M11-N5R) — the ONE curl-subprocess transport the fleet-side
runners ride. MC 12570's `_curl` moved VERBATIM out of scripts/pris_vakt.py
(the measured CF fact that made it: Cloudflare 403s python-urllib on
sibbamala.com, curl passes the edge), so ai_rek_pass (the /ai-rek runner)
and pris_vakt (the /pris runner) share ONE transport instead of forking a
second one — one mechanism, two callers. The body is byte-identical to the
MC 12570 original; the patch surface moved with it (tests monkeypatch
`curl_transport.subprocess.run`).
"""
import subprocess
import tempfile

CURL = "curl"                               # the production transport (MC 12570)
WATCHDOG_GRACE_S = 5                        # hard subprocess stop, wedged curl


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
