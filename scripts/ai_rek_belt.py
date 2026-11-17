"""MC 12617 (M11-N8b) — the generation belts the DA rounds put on the
runner, one module; MC 12643 (M11-N9a) adds the third. The concerns ride
together because all answer the same question BEFORE a byte reaches the
door: "is this generation allowed?"

  near-miss (DA c3 F-P2-2c, the correction the alias-table idea died of):
  a candidate whose wish_key does NOT join a graded shelf card but whose
  folded title/author SIMPLY LOOKS like one (the corpus title carrying a
  parenthetical subtitle tail the shelf grades without, 'del N' series
  suffixes, diacritic drift — the class measured live 2026-11-17: the
  corpus named the book X (Y), the shelf grades X at 5★) is an OWNERSHIP
  AMBIGUITY. `seed.book_key` alias-resolves
  AUTHOR names only (DA probe3) — the app's ONE spelling mechanism cannot
  repair a TITLE misspelling, so there is no legal way to unify the two
  spellings: the row is refused (fail-closed), never repaired. The same
  classifier serves the fleet-side corpus rebase (OUT/lane/n8b_rebase.py),
  so the rebase and the runtime gate can never drift apart — ONE
  implementation, two callers (the fleet's anti-drift rule). (The diary's
  and the corpus' own strings are named nowhere here: the exposure gate
  counts this file — title classes are described, never quoted.)

  rehearsal (DA c5 F-P4-1, the 0→1 sweep cliff): a `--full` run POSTs the
  full-swap envelope — rows still `new` that are ABSENT from it are
  DELETED door-side. A production full-swap that never rehearsed is one
  bad generation away from deleting the whole standing list, so a live
  `--full` requires a COMPLETED `--dry-run` rehearsal of the same corpus
  against the same library inside the same run window (the stamp below).
  The plain upsert mode needs no stamp — MC 12616's byte-identical default
  path stays byte-identical.

  read-title list (MC 12643, M11-N9a, the owner's ruling "A"): the
  graded-only join could not SEE the books she read without rating them
  (DA c9 F-P1-1: 3 of 23 live rows were exactly that class), so the door
  now answers GET /ai-rek/library-keys — every `bok` row as {titel,
  forfattare, status} — and this module reads it through the SAME door
  credential (the GET variant of curl_transport's `_curl_config`, ZERO
  token bytes on argv). Unreadable list = the reader REFUSES; the caller
  refuses the whole pass, fail-closed — an UNfiltered generation is
  never posted. The near-miss math and the stamp stay network-free:
  the corpus rebase (OUT/lane/n8b_rebase.py) imports the classifier and
  never calls this reader.

The near-miss math and the stamp are stdlib only; the shelf bytes arrive
as arguments and the stamp is a 0600 local file — only the keys reader
touches the wire, through curl_transport. The math here is verbatim the
DA c3 probe's (out/.tmp/da-c3/probe_join.py) — thresholds included — so a
corpus that passes the gate passes the probe that certified it.
"""
import difflib
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

from app import seed  # THE fold (seed.py §5.7), not a second one
from scripts.curl_transport import _curl_config   # THE door transport (MC 12643)

NEAR_MISS_TITLE_RATIO = 0.62   # the DA c3 probe's measured threshold
NEAR_MISS_AUTHOR_RATIO = 0.5
REHEARSAL_WINDOW_S = 3600      # "same invocation window": a --dry-run that
#                                completed within this window may authorize
#                                one --full run (moved by env, see below)


def near_miss_kandidater(kandidater, graded):
    """[(candidate, graded-card-nearest)] for every candidate that does not
    join but looks like a graded shelf card. Flags: folded title ratio
    >= 0.62 OR token containment (a >5-char title token appearing inside
    the shelf title or vice versa), AND author ratio >= 0.5 (or a missing
    author on one side — never a pass-port: an unpaired author can only
    WEAKEN a flag that is already up)."""
    traffade = []
    for r in kandidater:
        ct = seed._fold(r["title"])
        ca = seed._fold(r.get("author") or "")
        bast = None
        for c in graded:
            st = seed._fold(c["title"])
            sa = seed._fold(c["author"] or "")
            rt = difflib.SequenceMatcher(None, ct, st).ratio()
            ra = (difflib.SequenceMatcher(None, ca, sa).ratio()
                  if ca and sa else 0.0)
            subs = (ct in st or st in ct) or any(
                tok in st for tok in ct.split() if len(tok) > 5)
            if (rt >= NEAR_MISS_TITLE_RATIO or subs) and (ra >= NEAR_MISS_AUTHOR_RATIO or not ca):
                poang = rt + 0.5 * ra + (0.25 if subs else 0.0)
                if bast is None or poang > bast[0]:
                    bast = (poang, c)
        if bast is not None:
            traffade.append((r, bast[1]))
    return traffade


def _sha_fil(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rehearsal_stamp(base, library_url):
    """Path of the rehearsal stamp, keyed by (base, library) so two app
    targets can never authorize each other; the dir moves with env
    AI_REK_REHEARSAL_DIR (tests), default the system temp dir."""
    rot = Path(os.environ.get("AI_REK_REHEARSAL_DIR")
               or tempfile.gettempdir())
    nyckel = hashlib.sha256(f"{base}\n{library_url}".encode()).hexdigest()
    return rot / f"ai-rek-rehearsal-{nyckel[:16]}.json"


def rehearsal_skriv(base, library_url, corpus_path, *, accepted, kategorier):
    """The PROOF of a completed dry-run: written only when a --dry-run
    passed every gate and printed its rows (run_pass calls it on its own
    return-0 path). 0600, no secret bytes: counts, sha, ts."""
    stamp = {"base": base, "library": library_url,
             "corpus_sha256": _sha_fil(corpus_path),
             "accepted": accepted, "kategorier": sorted(kategorier),
             "ts": time.time()}
    vagen = rehearsal_stamp(base, library_url)
    vagen.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(vagen, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(stamp, fh)
    return vagen


def rehearsal_held(base, library_url, corpus_path):
    """(True, None) only when a dry-run rehearsal of THIS corpus (byte-sha)
    against THIS library completed inside the window; (False, anledningen)
    otherwise — refuse, never guess. The window moves with env
    AI_REK_REHEARSAL_WINDOW_S (tests), default REHEARSAL_WINDOW_S."""
    vagen = rehearsal_stamp(base, library_url)
    try:
        with open(vagen, encoding="utf-8") as fh:
            stamp = json.load(fh)
    except (OSError, ValueError):
        return False, ("ingen fullbordad --dry-run registrerad för den här "
                       "korpusen och det här biblioteket")
    if stamp.get("corpus_sha256") != _sha_fil(corpus_path):
        return False, "repetitionen gjordes på en annan korpus (sha skiljer)"
    if stamp.get("library") != library_url:
        return False, "repetitionen gjordes mot ett annat bibliotek"
    fönster = float(os.environ.get("AI_REK_REHEARSAL_WINDOW_S")
                    or REHEARSAL_WINDOW_S)
    if time.time() - float(stamp.get("ts") or 0) > fönster:
        return False, f"repetitionen är äldre än fönstret ({fönster:.0f} s)"
    return True, None


def read_library_keys(url, token, *, timeout_s=15):
    """MC 12643 (M11-N9a, the owner's ruling "A") — the COMPLETE read-title
    list through the SAME door and the SAME token the POST rides: the GET
    variant of the shared `_curl_config` transport (credential in the
    per-call 0600 config file, ZERO token bytes on argv — MC 12616; the
    default budget mirrors the runner's shelf GET). FAIL-CLOSED by
    construction: anything but a 200 whose body is a JSON LIST of
    {titel, forfattare, status} objects with a non-empty `titel` is an
    ERROR — the caller (run_pass) refuses the whole pass, exit 5. An
    unreadable list never becomes an unfiltered generation; the empty
    list is a legitimate answer (a shelf with zero bok rows)."""
    status, body = _curl_config([("X-Ai-Rek-Token", token)],
                                lambda config: ["--config", config, url],
                                timeout_s=timeout_s)
    if status != 200:
        return None, f"library-keys {status}"
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None, "library-keys: svaret är inte JSON"
    if (not isinstance(data, list)
            or any(not isinstance(n, dict)
                   or not isinstance(n.get("titel"), str)
                   or not n["titel"].strip() for n in data)):
        return None, "library-keys: inte en lista av {titel,…}-rader"
    return data, None
