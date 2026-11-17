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

pris_vakt's header-as-argv path stays byte-identical by card ruling (its
legs live in tests/test_pris_vakt.py, untouched); `_curl`'s signature is
backward-compatible (the stated reading, MC 12616).
"""
import json
import os
import socket
import time
from types import SimpleNamespace

from scripts import ai_rek_pass as rp
from scripts import curl_transport as ct
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
