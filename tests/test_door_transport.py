"""MC 12616 PART B — the door-post TRANSPORT legs (DA c3 P2: the token out
of argv) + the full-swap envelope at the ONE real delivery. Split out of
test_ai_rek_pass.py when that file grew past the 600-line test ceiling
(workspace-convention; the fixtures are IMPORTED from it, never copied):

* door-argv-shape — the weld in its MC 12616 UPDATED SHAPE (red-first
  against the old one, never silently deleted): the secret header rides a
  per-call 0600 `--config @<tmpfile>`, argv carries ZERO token bytes (not
  even the header name), the file is unlinked when the call returns; the
  old weld asserted `X-Ai-Rek-Token: <token>` INSIDE argv — exactly the
  /proc/<curl>/cmdline leak DA c3 reproduced.
* live-curl-cmdline — the DA reproduction AS A GATE: read the LIVE
  /proc/<curl-pid>/cmdline of the execed child during a stubbed post;
  ZERO token bytes where DA saw the secret verbatim.
* generation-envelope — full=True POSTs `{"generation": rows}`; the
  default mode is today's bare array byte-identically.

MC 12616 c5 FIX WAVE (DA F-P2-1): the "pris keeps header-as-argv" reading
was VOID — the card append and LEDGER:1079 charge BOTH callers and no
ruling ever pinned pris; pris_vakt.door_post now rides `_curl_config`
too, byte-identical ON THE WIRE, its weld updated in
tests/test_pris_vakt.py red-first, and the PRIS token gets its own live
/proc leg below. DA F-P3-1: the config guard also rejects BACKSLASH
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
import socket
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
    now rides a per-call 0600 `--config @<tmpfile>`, argv carries ZERO
    token bytes (not even the header NAME), the config content is read off
    disk only by this leg, and the file is unlinked when the call
    returns."""
    anrop = []

    class FakeCurl:
        """subprocess.run replaced wholesale; the --output file gets the
        canned door receipt — the real _curl runs above it. The config
        tmpfile is captured DURING the call (mode + bytes + path)."""

        def __call__(self, argv, **kw):
            cfg = argv[argv.index("--config") + 1]
            with open(cfg[1:], "rb") as fh:
                innehall = fh.read()
            anrop.append((argv, kw, cfg,
                          os.stat(cfg[1:]).st_mode & 0o777, innehall))
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
    assert cfg.startswith("@") and not os.path.exists(cfg[1:])  # unlinked
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
    verbatim there); green on the config transport, byte-identical on the
    wire (the weld leg in tests/test_pris_vakt.py pins the content)."""
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
                                   "a\x01b"])
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
