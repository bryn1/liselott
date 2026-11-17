"""MC 12601 (M11-N5R) — the ONE curl-subprocess transport the fleet-side
runners ride. MC 12570's `_curl` moved VERBATIM out of scripts/pris_vakt.py
(the measured CF fact that made it: Cloudflare 403s python-urllib on
sibbamala.com, curl passes the edge), so the runners shared ONE transport
instead of forking a second one. The body is byte-identical to the
MC 12570 original; the patch surface moved with it (tests monkeypatch
`curl_transport.subprocess.run`).

CALLERS TODAY (MC 12606, M11-N4b): ONE — `scripts/ai_rek_pass.py`, the
/ai-rek runner, which rides BOTH halves (`_curl` for its plain GETs,
`_curl_config` for the door POST). Since MC 12643 the runner's read-title
reader (`scripts/ai_rek_belt.read_library_keys`) rides `_curl_config` too —
still the ONE caller family, one secret delivery for every door call. The
second caller this file named for two cards, `pris_vakt` (the nightly pris
runner), is RETIRED with the price/sale feature by the owner's ruling; the
transport STAYS because the runner that outlived the feature still needs it.

MC 12616 (DA c3 P2) adds `_curl_config` beside `_curl`: header delivery
whose SECRET bytes never reach argv (the reproduced /proc/<curl>/cmdline
leak). `_curl`'s signature is UNCHANGED — it stays the plain path the
GETs ride. MC 12616 c5 (DA F-P2-1): the first wave's "pris keeps the
header-as-argv path" reading was VOID — the card append and LEDGER:1079
charge BOTH callers and no ruling ever pinned pris — so both door
runners then rode `_curl_config`: one secret delivery, not two.
MC 12616 fix-wave 2 (DA c6 F-P1-1 P1) TRUTHS the wire claim: c5's
"byte-identical ON THE WIRE" was asserted on FABRICATED curl results and
was FALSE — `--config @<path>` is silently ignored by curl (the @ form
is include-syntax for inside config files), so the header NEVER arrived.
The transport ships the PLAIN `--config <path>` form now, and WIRE
ARRIVAL + byte-identity to the header-as-argv form are held by REAL-
REQUEST legs against a local listener (tests/test_door_transport.py:
the …delivers_the_token_header_on_the_wire leg + the argv-form
byte-comparison leg, both re-cut on the surviving /ai-rek door by
MC 12606), not by in-process fixtures.
"""
import os
import re
import subprocess
import tempfile

CURL = "curl"                               # the production transport (MC 12570)
WATCHDOG_GRACE_S = 5                        # hard subprocess stop, wedged curl
_HOKNAVN = re.compile(r"[A-Za-z0-9:-]+")    # the config guard's name shape
#                                         (MC 12616 c5, DA F-P3-1) — the
#                                         shape the door header carries


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
    created 0600), curl reads them via the PLAIN `--config <path>` form,
    and the file is unlinked in the finally. The content is never echoed or logged: this
    function never prints, and `_curl`'s failure path answers (0, b"").
    THE PLAIN FORM (MC 12616 fix-wave 2, DA c6 F-P1-1 P1): curl gets the
    tmpfile path as `--config <path>` — NOT `--config @<path>`: the `@`
    is include-syntax for INSIDE config files, curl 7.81 parses "@/tmp/…"
    as a FILE NAMED that, WARNs once and SENDS THE REQUEST ANYWAY WITHOUT
    THE HEADER (measured 297 → 217 wire bytes). The old in-process legs
    could not see it — every c5 claim of wire identity was asserted on
    FABRICATED curl results and was FALSE. What is true now, and is held
    by REAL-WIRE legs (a local listener capturing the raw request, both
    doors): the header ARRIVES byte-exact, and the capture is BYTE-
    IDENTICAL to the header-as-argv form it replaces (port-normalized,
    test_config_delivery_is_wire_identical_to_the_argv_header_form).
    THE GUARD (MC 12616 c5 F-P3-1 + c6 F-P4-6 — curl expands BACKSLASH
    escapes inside the quoted value, measured as a genuine wire-newline
    injection; and printable NON-ASCII passes isprintable() but dies
    mid-WRITE after header #1's secret bytes are already in the file):
    EVERY pair is validated BEFORE any file exists — name full-matching
    [A-Za-z0-9:-]+, value ASCII, printable, and free of `"`, backslash,
    CR, LF — so a token value can never inject config lines and a
    rejected call creates NO file and writes NO bytes, every call shape.
    (The empty value is accepted — `header = "X: "\n` is inert; neither
    runner can produce one, DA c6 F-P4-6 note.) THE RESIDUE HONESTY
    (DA c6 F-P4-7): the best-effort double unlink covers TRANSIENT
    failures; a SIGTERM/SIGKILL between mkstemp and the finally — the
    killed-tick class — can still strand the 0600 file (five pre-fix
    witnesses on this host, stat-only). Signal-safe cleanup
    (tmpreaper/tmpfiles.d/handler) is a future runner card, NOT this
    transport's promise; `build_args(config_arg)` takes the PLAIN path,
    and the argv that reaches /proc carries ZERO secret bytes (legs: the
    live-curl-cmdline leg and the wire-delivery leg)."""
    for namn, varde in secret_headers:                # EVERY pair, BEFORE
        if not _HOKNAVN.fullmatch(namn):              # a single byte of
            raise ValueError("confighögardet ur formen — vägrar skriva")
        if not varde.isascii() or not varde.isprintable():   # c6 F-P4-6:
            raise ValueError("configvärdet ur formen — vägrar skriva")
        if any(c in varde for c in '"\\\r\n'):
            raise ValueError("configvärdet ur formen — vägrar skriva")
    fd, path = tempfile.mkstemp(prefix="curl-hdr-")
    try:
        with os.fdopen(fd, "w", encoding="ascii") as fh:
            for namn, varde in secret_headers:
                fh.write(f'header = "{namn}: {varde}"\n')
        return _curl(build_args(path), timeout_s=timeout_s,     # PLAIN
                     stdin_data=stdin_data)                     # form (c6)
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
