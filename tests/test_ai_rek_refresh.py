"""MC 12647 (M11-N11) — the REFRESH TRIGGER legs, OFFLINE (seams faked,
zero network — the drift legs additionally prove ZERO seam calls before
any shelf read). Owner ruling (chat 2026-11-17, verbatim): "Ai list
refreshes each 20 books graded". The law these legs pin:

  trigger              delta = (graded cards on the PUBLIC shelf now) -
                       (graded_count stored in the LAST ACCEPTED full-wave
                       record); delta >= 20 => the runner runs the dry-run
                       rehearsal + the full wave in the SAME invocation;
                       REFRESH_GRADED_DELTA == 20 is the owner's number
  not-due              delta < 20 (negative included) => exit 0 LOUD
                       "delta X/20", zero POST, zero lane asks
  missing record       NO accepted wave on record => NOT due (never a
                       surprise wave) + loud, exit 0, zero network at all
  stamp/record drift   an unreadable/shape-invalid/foreign record in the
                       shared state dir => ALARM, exit != 0, ZERO seam
                       calls (the stubs RAISE if anything touches them)
  record written       the record (graded_count + accepted + ts, 0600) is
                       written ONLY by an accepted FULL wave (door 2xx) —
                       never by a dry-run, never by upsert, never by a
                       refused door
  stamp carries it     the rehearsal stamp gains graded_count (the shelf
                       size the rehearsal actually saw)

The wrapper leg is a bash -n syntax weld on scripts/ai_rek_refresh_tick.sh;
the systemd unit FILES + systemd-analyze verify land agent-town-side
(infra/services/ai-rek/, MC 12647) — installing stays the orchestrator's.
"""
import json
import socket
import stat
import subprocess
from pathlib import Path

import pytest

from scripts import ai_rek_pass as rp
from scripts import ai_rek_refresh as rf
from tests.test_ai_rek_pass import (GRADERADE, FakeLane, FakePost, kör,
                                    korpus_tsv, library_med_html, shelf_html,
                                    svar_alla)

BASE = "https://sibbamala.test/liselott"
BIBL = BASE + "/bibliotek"


def _nej(*a, **k):                     # a touched seam IS the failure
    raise AssertionError("natverksanrop forvantat ej")


class StubPass:
    """Stand-in run_pass: records (dry_run, full) per call, returns canned
    exit codes in order — proves ORDER, not behaviour."""

    def __init__(self, koder=(0, 0)):
        self.calls, self.koder = [], list(koder)

    def __call__(self, corpus, library, base, *, dry_run=False, full=False,
                 **kw):
        self.calls.append((dry_run, full))
        return self.koder.pop(0)


def hyll_cards(n):
    """n graded cards: ONE shared author keeps the near-miss belt silent
    (every candidate carries an author, whose fold ratio to 'Annat Namn'
    stays < 0.5); distinct titles never strict-join the TITELORD rows."""
    return GRADERADE + [{"title": f"Hyllvärdig Bok {i:02d}",
                         "author": "Annat Namn", "rating": 4}
                        for i in range(n - 1)]


def state_dir(mp, tmp_path):
    mp.setenv("AI_REK_STATE_DIR", str(tmp_path / "state"))
    return tmp_path / "state"


def check(mp, tmp_path, *, record, graded_n, stub):
    """One check_refresh over pure stubs: the shelf seam answers `graded_n`
    graded cards, run_pass is the StubPass; every other seam RAISES."""
    d = state_dir(mp, tmp_path)
    if record is not None:
        rf.refresh_record_skriv(BASE, BIBL, graded_count=record, accepted=21)
    lines = []
    kod = rf.check_refresh(korpus_tsv(tmp_path / "corpus.tsv"), BIBL, BASE,
                           run_pass=stub,
                           get_library=lambda url: (hyll_cards(graded_n), None),
                           get_keys=_nej, lane=_nej, post=_nej,
                           say=lines.append)
    return kod, lines, d


# --- the owner's number + the not-due classes ---------------------------------

def test_refresh_trigger_is_twenty():
    assert rf.REFRESH_GRADED_DELTA == 20       # owner ruling, verbatim: 20


def test_missing_record_not_due_never_a_surprise_wave(tmp_path, monkeypatch):
    """No accepted wave on record => NOT due + loud, exit 0 — and the shelf
    is never even read (the record answers alone: zero seam calls)."""
    kod, lines, d = check(monkeypatch, tmp_path, record=None, graded_n=25,
                          stub=StubPass())
    assert kod == 0
    assert any("INTE DUE" in ln and "ingen accepterad" in ln for ln in lines)
    assert not (d / rf.refresh_record_name(BASE, BIBL)).exists()


@pytest.mark.parametrize("nu,gammal", [(119, 100), (100, 100), (95, 100)])
def test_delta_under_twenty_not_due_zero_wave(tmp_path, monkeypatch,
                                              nu, gammal):
    """delta < 20 (exact 19, zero, and a SHRUNKEN shelf) => exit 0 loud
    with the delta shown; run_pass never called — zero POST boomer."""
    kod, lines, _ = check(monkeypatch, tmp_path, record=gammal,
                          graded_n=nu, stub=StubPass())
    assert kod == 0
    assert any("INTE DUE" in ln and f"delta {nu - gammal}/20" in ln
               for ln in lines)


# --- the due class: rehearsal + wave in the SAME invocation ------------------

def test_delta_twenty_runs_rehearsal_then_full_in_one_invocation(
        tmp_path, monkeypatch):
    stub = StubPass()
    kod, lines, _ = check(monkeypatch, tmp_path, record=100, graded_n=120,
                          stub=stub)
    assert kod == 0
    assert any("REFRESH DUE" in ln and "delta 20/20" in ln for ln in lines)
    assert stub.calls == [(True, False), (False, True)]   # dry-run FIRST,


def test_delta_over_twenty_also_due(tmp_path, monkeypatch):
    stub = StubPass()
    kod, _, _ = check(monkeypatch, tmp_path, record=100, graded_n=125,
                      stub=stub)
    assert kod == 0 and stub.calls == [(True, False), (False, True)]


def test_refused_rehearsal_never_reaches_the_wave(tmp_path, monkeypatch):
    stub = StubPass(koder=(2,))               # the rehearsal refuses
    kod, lines, _ = check(monkeypatch, tmp_path, record=100, graded_n=120,
                          stub=stub)
    assert kod == 2                            # the refusal rides out
    assert stub.calls == [(True, False)]       # the wave never ran
    assert any("ALARM" in ln and "repetition" in ln for ln in lines)


def test_wave_exit_code_rides_out(tmp_path, monkeypatch):
    stub = StubPass(koder=(0, 5))              # the door refused the wave
    kod, _, _ = check(monkeypatch, tmp_path, record=100, graded_n=120,
                      stub=stub)
    assert kod == 5


# --- drift: fail loud, ZERO seam calls ----------------------------------------

@pytest.mark.parametrize("sudd", [
    b"inte json alls",                                        # garbage
    b"[]",                                                    # not a dict
    json.dumps({"base": BASE, "library": BIBL, "accepted": 21,
                "ts": 1.0}).encode(),                         # no graded_count
    json.dumps({"base": BASE, "library": BIBL, "graded_count": None,
                "accepted": 21, "ts": 1.0}).encode(),         # null count
    json.dumps({"base": BASE, "library": BIBL, "graded_count": -3,
                "accepted": 21, "ts": 1.0}).encode(),         # negative
    json.dumps({"base": BASE, "library": BIBL, "graded_count": "20",
                "accepted": 21, "ts": 1.0}).encode(),         # not an int
    json.dumps({"base": "https://annat.test/liselott",
                "library": BIBL, "graded_count": 100,
                "accepted": 21, "ts": 1.0}).encode(),         # foreign base
])
def test_drift_fails_loud_before_any_network(tmp_path, monkeypatch, sudd):
    d = state_dir(monkeypatch, tmp_path)
    d.mkdir(parents=True)
    (d / rf.refresh_record_name(BASE, BIBL)).write_bytes(sudd)
    lines = []
    kod = rf.check_refresh(korpus_tsv(tmp_path / "corpus.tsv"), BIBL, BASE,
                           run_pass=_nej, get_library=_nej, get_keys=_nej,
                           lane=_nej, post=_nej, say=lines.append)
    assert kod != 0
    assert any("ALARM" in ln and "drift" in ln for ln in lines)


# --- the accepted-wave record itself ------------------------------------------

def test_record_written_only_by_accepted_full_wave(tmp_path, monkeypatch):
    """kör's full=True face rides a REAL run_pass over faked seams: door
    2xx => the record (count + accepted + ts) lands, 0600 in a 0700 dir."""
    d = state_dir(monkeypatch, tmp_path)
    kod, lines, lane, post = kör(monkeypatch, tmp_path, full=True)
    assert kod == 0 and len(post.calls) == 1
    fill = d / rf.refresh_record_name(BASE, BIBL)
    rec = json.loads(fill.read_text(encoding="utf-8"))
    assert rec["graded_count"] == len(GRADERADE) == 1
    assert rec["accepted"] == 21 and rec["base"] == BASE
    assert isinstance(rec["ts"], float)
    assert stat.S_IMODE(fill.stat().st_mode) == 0o600
    assert stat.S_IMODE(d.stat().st_mode) == 0o700


@pytest.mark.parametrize("face", ["dry", "upsert", "door503"])
def test_record_never_written_by_dry_upsert_or_refused_door(
        tmp_path, monkeypatch, face):
    d = state_dir(monkeypatch, tmp_path)
    extra = {"post": FakePost(status=503)} if face == "door503" else {}
    kod, lines, _, post = kör(monkeypatch, tmp_path,
                              dry=(face == "dry"),
                              full=(face == "door503"), **extra)
    assert kod == (5 if face == "door503" else 0)
    assert not (d / rf.refresh_record_name(BASE, BIBL)).exists()


def test_rehearsal_stamp_carries_graded_count(tmp_path, monkeypatch):
    """The stamp records the shelf size the rehearsal ACTUALLY saw — the
    provenance the accepted-wave baseline rides."""
    state_dir(monkeypatch, tmp_path)
    kod, lines, lane, post = kör(monkeypatch, tmp_path, dry=True,
                                 graded=hyll_cards(7))
    assert kod == 0
    stamps = list(tmp_path.glob("ai-rek-rehearsal-*.json"))
    assert len(stamps) == 1
    assert json.loads(stamps[0].read_text(encoding="utf-8"))["graded_count"] \
        == 7


def test_check_refresh_end_to_end_delta_20_posts_and_rebases(
        tmp_path, monkeypatch):
    """The whole tick logic over faked wires ONLY: shelf 21 vs record 1 =>
    due => rehearsal + full wave in ONE invocation => exactly ONE full POST
    and the rebased record says 21."""
    d = state_dir(monkeypatch, tmp_path)
    rf.refresh_record_skriv(BASE, BIBL, graded_count=1, accepted=20)
    monkeypatch.setenv(rp.ENV_TOKEN, "a" * 64)
    monkeypatch.setenv("AI_REK_REHEARSAL_DIR", str(tmp_path))
    ts = korpus_tsv(tmp_path / "corpus.tsv")
    lib = library_med_html(shelf_html(hyll_cards(21)))
    post, lane = FakePost(), FakeLane(svar_alla(21))
    lines = []
    kod = rf.check_refresh(ts, BIBL, BASE, run_pass=rp.run_pass,
                           get_library=lib, get_keys=lambda u, t: ([], None),
                           lane=lane, post=post, say=lines.append)
    assert kod == 0
    assert any("REFRESH DUE" in ln and "delta 20/20" in ln for ln in lines)
    assert len(post.calls) == 1 and post.calls[0][3] is True   # full only
    assert lane.calls == 2                           # one ask per wave pass
    rec = json.loads((d / rf.refresh_record_name(BASE, BIBL))
                     .read_text(encoding="utf-8"))
    assert rec["graded_count"] == 21 and rec["accepted"] == 21


# --- the CLI + the wrapper -----------------------------------------------------

def test_main_check_refresh_flag(tmp_path, monkeypatch, capsys):
    """--check-refresh through main with NO record: not-due exit 0, loud on
    stdout, and no socket may even exist on that path."""
    monkeypatch.setenv("AI_REK_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv(rp.ENV_URL, raising=False)
    monkeypatch.delenv(rp.ENV_TOKEN, raising=False)
    monkeypatch.setattr(socket, "socket", _nej)
    monkeypatch.setattr(socket, "create_connection", _nej)
    kod = rp.main(["--corpus", str(korpus_tsv(tmp_path / "corpus.tsv")),
                   "--check-refresh"])
    assert kod == 0
    assert "INTE DUE" in capsys.readouterr().out


def test_wrapper_script_is_valid_bash():
    p = Path(rp.__file__).with_name("ai_rek_refresh_tick.sh")
    assert p.is_file(), "scripts/ai_rek_refresh_tick.sh saknas"
    r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
