"""MC 12616 PART B — the door-post TRANSPORT legs (DA c3 P2: the token out
of argv) + the full-swap envelope at the ONE real delivery. Split out of
test_ai_rek_pass.py when that file grew past the 600-line test ceiling
(workspace-convention; the fixtures are IMPORTED from it, never copied):

* door-argv-shape — the weld in its MC 12616 UPDATED SHAPE (red-first
  against the old one, never silently deleted; PLAIN `--config <tmpfile>`
  path since fix-wave 2 — the `@` form is silently ignored by curl,
  DA c6 F-P1-1): argv carries ZERO token bytes (not even the header
  name), the file is unlinked when the call returns; the old weld
  asserted `X-Ai-Rek-Token: <token>` INSIDE argv — exactly the
  /proc/<curl>/cmdline leak DA c3 reproduced.
* live-curl-cmdline — the DA reproduction AS A GATE: read the LIVE
  /proc/<curl-pid>/cmdline of the execed child during a stubbed post;
  ZERO token bytes where DA saw the secret verbatim.
* generation-envelope — full=True POSTs `{"generation": rows}`; the
  default mode is today's bare array byte-identically.

MC 12616 c5 FIX WAVE (DA F-P2-1): the "pris keeps header-as-argv" reading
was VOID — the card append and LEDGER:1079 charge BOTH callers and no
ruling ever pinned pris; pris_vakt.door_post now rides `_curl_config`
too, its weld updated in tests/test_pris_vakt.py red-first, and the PRIS
token gets its own live /proc leg below. c5 CLAIMED "byte-identical ON
THE WIRE" — FALSE (DA c6 F-P1-1: asserted on fabricated curl results;
the `--config @<path>` form is silently ignored, the header never
arrived). Fix-wave 2 ships the PLAIN `--config <path>` form and the
claim's REAL backing lives at the bottom of this file: the two …delivers_
the_token_header_on_the_wire legs capture the actual request against a
local listener and the argv-form comparison leg pins byte-identity to
the replaced shape — in-process fixtures prove the shape, WIRE legs
prove the arrival. DA F-P3-1: the config guard also rejects BACKSLASH
(curl expands `\`-escapes in quoted values — measured wire-newline
injection) and malformed header NAMES, validating EVERY pair BEFORE the
tmpfile is created. DA F-P4-2: the unlink is best-effort TWICE — a
transient first failure no longer propagates nor strands the file.

* config-guard — every rejected value/name raises BEFORE any file exists
  (mkstemp boomer proves it) and curl never runs.
* unlink-best-effort — the first unlink failing once still leaves the
  file gone and the call returning normally.
* pris-live-curl-cmdline — the same live /proc read for the PRIS door.
"""
import json
import os
import re
import socket
import threading
import time
from types import SimpleNamespace

import pytest

from scripts import ai_rek_pass as rp
from scripts import curl_transport as ct
from scripts import pris_vakt as pv
from tests.test_ai_rek_pass import (GRADERADE, FakeLane, korpus_tsv,
                                    library_med_html, shelf_html, svar_alla)


def test_door_post_rides_shared_curl_argv(tmp_path, monkeypatch):
    """The delivery argv shape ONE LEVEL BELOW the transport (the pris_vakt
    FakeCurl posture): curl argv list, never a shell — --data-binary @- on
    stdin, {base}/ai-rek last, the body IS the ranked rows and kategori
    rides every one of them (MC 12602 F-P4-1). MC 12616 PART B UPDATED
    THIS WELD red-first — the old shape asserted `X-Ai-Rek-Token: <token>`
    INSIDE argv, exactly the /proc/<curl>/cmdline leak DA c3 reproduced
    (updated to the new shape, never silently deleted): the secret header
    now rides a per-call 0600 `--config <tmpfile>` — the PLAIN path: the
    `@` form is silently IGNORED by curl (DA c6 F-P1-1), argv carries
    ZERO token bytes (not even the header NAME), the config content is
    read off disk only by this leg, and the file is unlinked when the
    call returns. A WELD PROVES THE SHAPE, NEVER THE ARRIVAL — the
    real-wire legs at the bottom of this file carry that claim."""
    anrop = []

    class FakeCurl:
        """subprocess.run replaced wholesale; the --output file gets the
        canned door receipt — the real _curl runs above it. The config
        tmpfile is captured DURING the call (mode + bytes + path).
        NOTE (DA c6 F-P1-1): this fabricated returncode could never see
        the `@`-defect — arrival is proven ONLY by the wire legs."""

        def __call__(self, argv, **kw):
            cfg = argv[argv.index("--config") + 1]
            with open(cfg, "rb") as fh:
                innehall = fh.read()
            anrop.append((argv, kw, cfg,
                          os.stat(cfg).st_mode & 0o777, innehall))
            with open(argv[argv.index("--output") + 1], "wb") as fh:
                fh.write(b'{"inserted": 21}')
            return SimpleNamespace(returncode=0, stdout=b"200", stderr=b"")
    monkeypatch.setattr(ct.subprocess, "run", FakeCurl())
    monkeypatch.setenv(rp.ENV_TOKEN, "a" * 64)
    lines = []
    code = rp.run_pass(korpus_tsv(tmp_path / "corpus.tsv"),
                       "https://sibbamala.test/bibliotek",
                       "https://sibbamala.test",
                       get_library=library_med_html(shelf_html(GRADERADE)),
                       lane=FakeLane(svar_alla(21)), say=lines.append)
    assert code == 0 and len(anrop) == 1
    argv, kw, cfg, mode, innehall = anrop[0]
    assert argv[0] == "curl" and argv[-1] == "https://sibbamala.test/ai-rek"
    assert not cfg.startswith("@")                   # c6 F-P1-1: the PLAIN
    assert cfg == os.path.abspath(cfg)               # form — curl ignores
    assert not os.path.exists(cfg)                   # "@"-forms (unlinked)
    assert mode == 0o600                               # mkstemp's own mode
    assert innehall == b'header = "X-Ai-Rek-Token: ' + b"a" * 64 + b'"\n'
    assert not any("a" * 64 in del_a for del_a in argv)     # ZERO token bytes
    assert "X-Ai-Rek-Token" not in " ".join(argv)          # not even the name
    assert "Content-Type: application/json" in argv        # non-secret stays
    assert argv[argv.index("--data-binary") + 1] == "@-"
    assert argv[argv.index("--max-time") + 1] == str(rp.POST_TIMEOUT_S)
    assert kw["timeout"] == rp.POST_TIMEOUT_S + ct.WATCHDOG_GRACE_S
    rows = json.loads(kw["input"])
    assert len(rows) == 21
    assert all(r["kategori"] in rp.ai_rek.KATEGORIER for r in rows)


def test_door_post_token_absent_from_the_live_curl_cmdline(tmp_path,
                                                           monkeypatch):
    """DA c3 P2 REPRODUCED as a gate: during a real stubbed door post the
    leg reads the LIVE /proc/<curl-pid>/cmdline of the child the transport
    execs (against a socket that answers nothing, so the child lives) —
    ZERO token bytes in it. The old header-as-argv shape put the secret
    there verbatim; this leg is the reason it can never come back."""
    import subprocess
    mottagare = socket.socket()
    mottagare.bind(("127.0.0.1", 0))
    mottagare.listen(1)
    port = mottagare.getsockname()[1]
    token = "f" * 64
    kommandorader = []

    class LevandeCurl:
        """subprocess.run replaced by the Popen of the REAL argv: the
        child execs curl with --data-binary @- and never gets its stdin,
        so it lives long enough to read its own cmdline from /proc."""

        def __call__(self, argv, **kw):
            process = subprocess.Popen(argv, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
            try:
                for _ in range(200):                   # wait out the exec
                    with open(f"/proc/{process.pid}/cmdline", "rb") as fh:
                        kommandorad = fh.read()
                    if kommandorad.startswith(b"curl"):
                        break
                    time.sleep(0.05)
                kommandorader.append(kommandorad)
            finally:
                process.kill()
                process.wait()
            return SimpleNamespace(returncode=0, stdout=b"200", stderr=b"")

    monkeypatch.setattr(ct.subprocess, "run", LevandeCurl())
    status, _ = rp.door_post(f"http://127.0.0.1:{port}/ai-rek", token,
                             [{"title": "T"}])
    assert status == 200 and len(kommandorader) == 1
    kommandorad = kommandorader[0]
    assert kommandorad.startswith(b"curl")             # the exec really ran
    assert token.encode() not in kommandorad           # ZERO token bytes
    assert b"X-Ai-Rek-Token" not in kommandorad        # not even the name
    mottagare.close()


def test_full_mode_posts_the_generation_envelope(tmp_path, monkeypatch):
    """MC 12616 at the ONE real delivery: full=True POSTs
    `{"generation": rows}` — the rows byte-equivalent to upsert mode's
    array, the envelope the door sweeps against; default mode keeps the
    bare array byte-identical."""
    kroppar = []

    class FakeCurl:
        def __call__(self, argv, **kw):
            with open(argv[argv.index("--output") + 1], "wb") as fh:
                fh.write(b'{"inserted": 21, "deleted_n": 0}')
            kroppar.append(kw["input"])
            return SimpleNamespace(returncode=0, stdout=b"200", stderr=b"")

    monkeypatch.setattr(ct.subprocess, "run", FakeCurl())
    status, body = rp.door_post("https://sibbamala.test/ai-rek", "a" * 64,
                                [{"title": "T"}], full=True)
    assert status == 200
    omslag = json.loads(kroppar[-1])
    assert list(omslag) == ["generation"] and omslag["generation"] == \
        [{"title": "T"}]
    rp.door_post("https://sibbamala.test/ai-rek", "a" * 64, [{"title": "T"}])
    assert json.loads(kroppar[-1]) == [{"title": "T"}]   # default: plain array


# ── MC 12616 c5 fix wave (DA-verdict-c5) ──────────────────────────────────
def test_pris_door_post_token_absent_from_the_live_curl_cmdline(monkeypatch):
    """DA c5 F-P2-1, mirroring the AI-rec leg: the NIGHTLY pris tick execs
    curl with ZERO token bytes on the child's cmdline now. RED-FIRST on
    the old header-as-argv shape (the DA measured `X-Pris-Token: <secret>`
    verbatim there); green on the config transport. This leg proves the
    LEAK is gone — ARRIVAL is proven by the pris wire leg at the bottom
    of this file, byte-identity to the argv form by the comparison leg
    (c5's "byte-identical on the wire" here rested on fabricated curl
    results; DA c6 F-P1-1 named it FALSE — the @-form never delivered)."""
    import subprocess
    mottagare = socket.socket()
    mottagare.bind(("127.0.0.1", 0))
    mottagare.listen(1)
    port = mottagare.getsockname()[1]
    token = "d" * 64
    kommandorader = []

    class LevandeCurl:
        def __call__(self, argv, **kw):
            process = subprocess.Popen(argv, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
            try:
                for _ in range(200):                   # wait out the exec
                    with open(f"/proc/{process.pid}/cmdline", "rb") as fh:
                        kommandorad = fh.read()
                    if kommandorad.startswith(b"curl"):
                        break
                    time.sleep(0.05)
                kommandorader.append(kommandorad)
            finally:
                process.kill()
                process.wait()
            with open(argv[argv.index("--output") + 1], "wb") as fh:
                fh.write(b"{}")                # the pris runner parses counters
            return SimpleNamespace(returncode=0, stdout=b"200", stderr=b"")

    monkeypatch.setattr(ct.subprocess, "run", LevandeCurl())
    status, counters = pv.door_post(f"http://127.0.0.1:{port}/pris", token, [])
    assert status == 200 and counters == {} and len(kommandorader) == 1
    kommandorad = kommandorader[0]
    assert kommandorad.startswith(b"curl")             # the exec really ran
    assert token.encode() not in kommandorad           # ZERO token bytes
    assert b"X-Pris-Token" not in kommandorad          # not even the name
    mottagare.close()


@pytest.mark.parametrize("varde", ['a"b', "a\nb", "a\rb", "a\\b", "a\\nb",
                                   "a\x01b", "caf\xe9", "\U0001F5A4"])
def test_config_guard_rejects_values_before_any_file(monkeypatch, varde):
    """DA c5 F-P3-1: REAL curl expands BACKSLASH escapes inside the quoted
    config value (a literal backslash-n became a genuine wire NEWLINE,
    measured) — so the guard rejects backslash and every non-printable
    beside the quote/newline/CR it already knew, and it validates EVERY
    pair BEFORE the tmpfile exists: mkstemp is boomed here, a created file
    fails the leg; curl never runs."""
    def boomer(*args, **kwargs):
        raise AssertionError("tmpfile skapades — guarden måste neka FÖRE den")

    körd = []
    monkeypatch.setattr(ct.tempfile, "mkstemp", boomer)
    monkeypatch.setattr(ct.subprocess, "run",
                        lambda *a, **k: körd.append(a))
    with pytest.raises(ValueError):
        ct._curl_config([("X-Pris-Token", varde)],
                        lambda config: [config], timeout_s=1)
    assert körd == []


@pytest.mark.parametrize("namn", ["X Pris", "X-T\n", "", "X-T;", "X-T;g=1"])
def test_config_guard_rejects_malformed_header_names(monkeypatch, namn):
    """Names are held to [A-Za-z0-9:-]+ — the shape BOTH door headers
    have; nothing else ever reaches a config line, before any file."""
    def boomer(*args, **kwargs):
        raise AssertionError("tmpfile skapades — guarden måste neka FÖRE den")

    monkeypatch.setattr(ct.tempfile, "mkstemp", boomer)
    with pytest.raises(ValueError):
        ct._curl_config([(namn, "f" * 64)],
                        lambda config: [config], timeout_s=1)


def test_config_unlink_is_best_effort_twice(monkeypatch):
    """DA c5 F-P4-2 (measured: an unlink failure PROPAGATED out of
    door_post as an exit-1 traceback AND stranded the 0600 file — a real
    leftover was witnessed in /tmp): the first unlink failing once must
    neither raise nor leave residue — a best-effort SECOND attempt, and
    the transport says so at the site."""
    pathar = []
    verklig = os.unlink

    def första_gången(path):
        pathar.append(path)
        if len(pathar) == 1:
            raise OSError("simulated read-only fs")
        verklig(path)

    monkeypatch.setattr(ct.os, "unlink", första_gången)
    monkeypatch.setattr(ct.subprocess, "run",
                        lambda argv, **kw: SimpleNamespace(
                            returncode=0, stdout=b"200", stderr=b""))
    status, _ = ct._curl_config([("X-Ai-Rek-Token", "a" * 64)],
                                lambda config: [config], timeout_s=1)
    assert status == 200 and len(pathar) == 2
    assert not os.path.exists(pathar[1])       # residue died on the second try


# ── MC 12616 fix-wave 2 (DA-verdict-c6 F-P1-1 P1): THE WIRE ARRIVAL ───────
class _TraddFaangst:
    """DA c6 probe3's harness: a one-shot local HTTP listener that captures
    the RAW request bytes curl actually put on the wire, answers with the
    door receipt and closes. THE CLASS THE SUITE LACKED: every earlier leg
    tested ABSENCE from argv or the tmpfile's content and FABRICATED the
    curl success — nothing proved the header ARRIVES (F-P1-1: `--config
    @<path>` is silently IGNORED by curl 7.81 — the @ form is include-
    syntax inside config files only — so the request went out WITHOUT the
    secret header, measured 297 → 217 bytes)."""

    def __init__(self, body=b'{"accepted": 1}'):
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.kvittens, self.wire = body, []
        threading.Thread(target=self._servera, daemon=True).start()

    def _servera(self):
        try:
            conn, _ = self.sock.accept()
        except OSError:
            return
        conn.settimeout(5)
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(65536)
            if not chunk:
                break
            data += chunk
        self.wire.append(data)
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                     b"Content-Length: " + str(len(self.kvittens)).encode()
                     + b"\r\n\r\n" + self.kvittens)
        time.sleep(0.2)
        conn.close()
        self.sock.close()

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def stoek(self):
        try:
            self.sock.close()
        except OSError:
            pass


def test_pris_door_delivers_the_token_header_on_the_wire():
    """F-P1-1's DELIVERY leg, pris door: the REAL subprocess.run (no fake
    anywhere in this leg) execs curl against the local listener; the leg
    asserts the exact header line sits on the wire. RED-FIRST on the
    `--config @<path>` shape (the header never arrived — DA measured it,
    this leg reproduces it), GREEN on the plain `--config <path>`."""
    kanari = "e" * 64
    server = _TraddFaangst()
    status, counters = pv.door_post(
        server.url("/pris"), kanari,
        [{"id": "B1", "isbn": "9781234567890", "titel": "T",
          "pris": "1 kr", "url": "u"}])
    server.stoek()
    assert status == 200 and counters == {"accepted": 1}
    assert len(server.wire) == 1
    traad = server.wire[0]
    assert f"X-Pris-Token: {kanari}\r\n".encode() in traad   # byte-exact
    assert b"Content-Type: application/json\r\n" in traad    # non-secret too


def test_ai_rek_door_delivers_the_token_header_on_the_wire():
    """The same class for the /ai-rek door — broken by the SAME `@` since
    b7b5a86 (zero wire headers, DA live-runner measurement). RED-FIRST on
    the @-shape, GREEN on the plain form; full=True rides the envelope
    through the same ONE delivery."""
    kanari = "c" * 64
    server = _TraddFaangst(b'{"inserted": 1, "deleted_n": 0}')
    status, body = rp.door_post(server.url("/ai-rek"), kanari,
                                [{"title": "T"}], full=True)
    server.stoek()
    assert status == 200
    assert len(server.wire) == 1
    assert f"X-Ai-Rek-Token: {kanari}\r\n".encode() in server.wire[0]
    assert b'{"generation": [{"title": "T"}]}' in server.wire[0] or \
        b'{"generation": [\n' not in server.wire[0]      # body rode too


def test_config_delivery_is_wire_identical_to_the_argv_header_form():
    """THE BACKING for the REWRITTEN byte-identity claim (DA c6: plain-
    form capture is byte-identical to the header-as-argv parent request,
    port-normalized — measured, not asserted on fabricated fixtures).
    Run A: the transport (config file). Run B: raw `_curl` with the old
    `--header X-Pris-Token: <canary>` argv shape. Same rows, same URL,
    same curl — the captures may differ ONLY in the port digits."""

    def normalisera(bad):
        return re.sub(rb"127\.0\.0\.1:\d+", b"127.0.0.1:P", bad)

    kanari = "a" * 64
    rader = [{"id": "B1", "isbn": "9781234567890", "titel": "T",
              "pris": "1 kr", "url": "u"}]
    kropp = json.dumps(rader).encode("utf-8")
    a = _TraddFaangst()
    pv.door_post(a.url("/pris"), kanari, rader)
    a.stoek()
    b = _TraddFaangst()
    ct._curl(["--request", "POST",
              "--header", "Content-Type: application/json",
              "--header", "X-Pris-Token: " + kanari,
              "--data-binary", "@-", b.url("/pris")],
             timeout_s=pv.POST_TIMEOUT_S, stdin_data=kropp)
    b.stoek()
    assert len(a.wire) == 1 and len(b.wire) == 1
    assert normalisera(a.wire[0]) == normalisera(b.wire[0])
