"""MC 12647 (M11-N11) — the REFRESH TRIGGER: the state and the decision
behind the owner's ruling (chat 2026-11-17, verbatim): "Ai list refreshes
each 20 books graded". The question this module answers, one concern:
"WHAT WAVE WAS ACCEPTED LAST, against how many graded books, and is a new
one due?"

  The record: every ACCEPTED FULL WAVE (door answered 2xx on the --full
  envelope) leaves an accepted-wave record — {base, library, graded_count,
  accepted, ts} — keyed by (base, library) exactly like the rehearsal
  stamp. `graded_count` is the number of graded cards on the PUBLIC shelf
  AT that wave; it is the baseline the next delta is measured from.

  The decision (`check_refresh`, mode --check-refresh): read the record
  BEFORE any network. No record => NOT due + loud (never a surprise wave;
  an un-baselined shelf is an operator setup, not a trigger). Drift (an
  unreadable / shape-invalid / foreign record) => ALARM, exit 2, ZERO
  network — fail loud, refuse, never guess. Otherwise count the current
  public shelf through the SAME seam the runner reads it with: delta <
  REFRESH_GRADED_DELTA => exit 0 loud "not due (delta X/20)"; delta >= 20
  => run the dry-run REHEARSAL first and, if it completed, the FULL WAVE,
  both in the SAME invocation (the rehearsal belt is unchanged — the wave
  it authorizes is the one the runner would refuse un-rehearsed).

  The state lives fleet-side in the runner state dir (env
  AI_REK_STATE_DIR; default /home/claudecode/.liselott-rek — NOT the
  repo; README documents the path): 0700 dir, 0600 files, no secret
  bytes — counts and a timestamp, like the rehearsal stamp.

No network happens HERE: `check_refresh` receives the wave runner
(`run_pass`) and the shelf reader (`get_library`) as seams — the runner
wires the real ones in main (importing the runner HERE would only create
a cycle), tests hand in stubs. The wrapper (scripts/ai_rek_refresh_tick.sh)
and the systemd unit files (agent-town infra/services/ai-rek/) are the
production callers; installing the timer stays the orchestrator's.
ONE tick at a time is a DEPLOYMENT property: the wrapper's flock IS the
serializer, and a concurrent full-swap is legal door-side (the later wave
wins, never a mixed generation) — the residual window is a manual
--check-refresh beside the timer (DA c12 F-DA12-7, accepted-and-recorded).
"""
import hashlib
import json
import os
import time
from pathlib import Path

REFRESH_GRADED_DELTA = 20               # the owner's number, verbatim:
#                                 "Ai list refreshes each 20 books graded"
STATE_DIR_DEFAULT = "/home/claudecode/.liselott-rek"


def state_dir():
    """The shared fleet state dir for the accepted-wave RECORDS (+ the
    wrapper's tick.log/tick.lock). Rehearsal stamps are NOT here: they
    stay in the belt's own rehearsal-dir (env AI_REK_REHEARSAL_DIR, else
    system tmp — under systemd's PrivateTmp that is the tick's private
    tmp, which is exactly right: a stale stamp never authorizes a later
    --full. DA c12 F-DA12-6, docs fixed to truth). Tests move this dir
    with env AI_REK_STATE_DIR."""
    return Path(os.environ.get("AI_REK_STATE_DIR") or STATE_DIR_DEFAULT)


def refresh_record_name(base, library_url):
    """File name keyed by (base, library) — the SAME key idiom as the
    rehearsal stamp, so two app targets can never baseline each other."""
    nyckel = hashlib.sha256(f"{base}\n{library_url}".encode()).hexdigest()
    return f"ai-rek-wave-{nyckel[:16]}.json"


def refresh_record_path(base, library_url):
    return state_dir() / refresh_record_name(base, library_url)


def refresh_record_läs(base, library_url):
    """(record, None) | (None, None) ABSENT | (None, anledningen) DRIFT.
    Absence is NOT drift: the caller answers NOT due (never a surprise
    wave). An unreadable, shape-invalid or FOREIGN (base/library) record
    IS: the on-disk state disagrees with itself — refuse before any
    network, fix the state, never guess a baseline."""
    vägen = refresh_record_path(base, library_url)
    try:
        with open(vägen, encoding="utf-8") as fh:
            record = json.load(fh)
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError) as e:
        return None, f"{vägen.name}: inte läsbar JSON ({type(e).__name__})"
    if not isinstance(record, dict):
        return None, (f"{vägen.name}: inte ett objekt med "
                      "base/library/graded_count/accepted/ts")
    fel = []
    graded, accepted = record.get("graded_count"), record.get("accepted")
    ts = record.get("ts")
    if not (isinstance(graded, int) and not isinstance(graded, bool)
            and graded >= 0):
        fel.append(f"graded_count {graded!r}")
    if not (isinstance(accepted, int) and not isinstance(accepted, bool)
            and accepted >= 0):
        fel.append(f"accepted {accepted!r}")
    if (isinstance(ts, bool)
            or not isinstance(ts, (int, float))):
        fel.append(f"ts {ts!r}")
    if fel:
        return None, f"{vägen.name}: fält utanför domän: {', '.join(fel)}"
    if record.get("base") != base or record.get("library") != library_url:
        return None, (f"{vägen.name}: beskriver {record.get('base')!r}/"
                      f"{record.get('library')!r}, inte den här körningen")
    return record, None


def refresh_record_skriv(base, library_url, *, graded_count, accepted):
    """The PROOF of an accepted full wave — the refresh baseline the next
    delta measures from. run_pass calls it ONLY on its door-accepted full
    path (never dry-run, never upsert, never a refused door). 0600 file
    in a 0700 state dir, no secret bytes: counts + ts, rehearsal-style."""
    rot = state_dir()
    rot.mkdir(parents=True, exist_ok=True, mode=0o700)
    record = {"base": base, "library": library_url,
              "graded_count": int(graded_count), "accepted": int(accepted),
              "ts": time.time()}
    vägen = refresh_record_path(base, library_url)
    fd = os.open(vägen, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(record, fh)
    return vägen


def check_refresh(corpus_path, library_url, base, *, run_pass, get_library,
                  say=None, get_keys=None, lane=None, post=None):
    """Mode --check-refresh as a function; returns the exit code (0 ok /
    not due; 2 drift or refused shelf or a refused rehearsal; else the
    wave's own code rides out). The record answers BEFORE the shelf is
    read (drift and absence cost zero network); only a DUE wave touches
    the door, and it touches it exactly as the runner always has:
    rehearsal first, full wave second, SAME invocation, unchanged belts.
    `run_pass`/`get_library` are seams (the runner wires the real ones;
    importing it here would only create a cycle)."""
    say = say or (lambda line: print(line, flush=True))
    record, drift = refresh_record_läs(base, library_url)
    if drift:
        say(f"ALARM refresh-drift: {drift} — fail-closed: noll nätverk, "
            "noll POST — laga delkatalogen, kör om")
        return 2
    if record is None:
        say("REK REFRESH INTE DUE: ingen accepterad full våg registrerad "
            "för den här dörren — kör ingen våg (aldrig en "
            "överraskningsvåg; sätt baslinjen med en godkänd --full)")
        return 0
    graded, fel = get_library(library_url)
    if graded is None:
        say(f"ALARM bibliotek avvisat: {fel} — noll POST")
        return 2
    if not graded:
        # F-DA12-4 (DA c12): zero parsed cards on a 200 page is a CF
        # interstitial / reader-template break, NOT a shelf that shrank —
        # the delta math below would answer "not due (-221)" and the unit
        # would report success on a library read that FAILED. Same
        # fail-closed floor as the runner's own taste gate, same words.
        say("ALARM smakprofil tom: biblioteket gav noll betygssatta rader "
            "— vägrar refresh (ingen 'baserat på hyllan' utan hyllan; en "
            "tom läsning är ett läsfel, inte ett delta) — noll POST")
        return 2
    delta = len(graded) - record["graded_count"]
    if delta < REFRESH_GRADED_DELTA:
        say(f"REK REFRESH INTE DUE: delta {delta}/{REFRESH_GRADED_DELTA} "
            f"betygssatta sedan accepterad våg ({record['graded_count']} "
            f"→ {len(graded)}) — kör ingen våg")
        return 0
    say(f"REK REFRESH DUE: delta {delta}/{REFRESH_GRADED_DELTA} "
        f"({record['graded_count']} → {len(graded)}) — kör "
        "--dry-run-repetition + full våg i samma anrop")
    våg = {"get_library": get_library, "say": say,
           "get_keys": get_keys, "lane": lane, "post": post}
    våg = {k: v for k, v in våg.items() if v is not None}
    kod = run_pass(corpus_path, library_url, base, dry_run=True, **våg)
    if kod != 0:
        say(f"ALARM refresh-repetition nekad (exit {kod}) — ingen våg")
        return kod
    return run_pass(corpus_path, library_url, base, full=True, **våg)
