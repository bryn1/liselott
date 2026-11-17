#!/usr/bin/env python3
# coding-discipline header reason (DA c11 F-DA11-3 closed: the clause sits
# INSIDE the gate's first-5-line window): 455 lines > 400 — the WHOLE
# generation contract (corpus shape, graded+read join, code gates, door
# delivery, refresh baseline) is one unchecked-nothing-can-pass chain:
# "between corpus.tsv and the door there is exactly one path". The split
# MC 12647 ran by concern moved the Lane E ask + its answer gates to
# scripts/ai_rek_lane.py and the refresh trigger to scripts/ai_rek_refresh.py.
"""MC 12601 (M11-N5R) — the generation runner for "AI rekommenderar".

Runs FLEET-side (VM350), never inside the app: reads the PUBLIC shelf
HTML, joins the corpus against it, asks Lane E to rank + reason, POSTs
/ai-rek. NO DB access, ever — the shelf's public bytes are the library.

Inputs:
  --library  the public shelf https://sibbamala.com/liselott/bibliotek
             (curl_transport — urllib 403'd at the CF edge, curl passes;
             cards public per owner scope; pris_parse.read_graded parses
             title/author/rating off the app's own _bokkort.html markup)
  --corpus   the fleet corpus TSV (26 rows, tab, 13 cols — the N1 output
             .audits/202611161817-aae834ce-n1/out/corpus.tsv)

Join (vs library): corpus rows whose BOOK the shelf already grades are
DROPPED, and since MC 12643 (owner ruling "A" — chat 2026-11-17, accepting:
the generator gets the COMPLETE read-title list via the existing machine
door; public scope unchanged, graded + wishlist only; books she has READ
are never recommended again) so is EVERY bok row GET /ai-rek/library-keys
answers, all statuses (DA c9 F-P1-1: 485 read-but-unrated books were
invisible to the graded-only join). Identity is THE app's OWN chain,
imported read-only: `onska.wish_key` (§5.3 seed.book_key, authors-only
aliases) + the isbn13 lane — ONE mechanism, the `_samma_bock` twin.

The ask (Lane E http://192.168.5.223:8888/v1/chat/completions): the ONE
compiled-default envelope idiom of scripts/cover_pass.py — one model id,
temperature 0, reasoning_effort low on both layers; urllib rides Lane E
(LAN-side, no CF edge) exactly as cover_pass's vision leg does. The prompt
carries her GRADED taste profile (every card + rating) and the corpus
rows; fit must be justified BY the profile and the model may ONLY rank +
reason over the corpus rows it is handed. Since MC 12647 the ask and the
gates vetting its answer live in scripts/ai_rek_lane.py (split by
concern); this module re-exports every name — ONE import surface.

Gates BEFORE a byte reaches the door (all in code, none in the prompt):
  hallucination  a returned isbn13 absent from the loaded corpus => row
                 REJECTED (`_validera`, carry N3: POSTed isbn in corpus).
  fit            non-finite / bool / outside [0,1] => row REJECTED:
                 REFUSE, never clamp — app/ai_rek._obs shape-rejects the
                 same values; a silent clamp would forge a score.
  identity       dedupe by isbn UNION wish_key-normalized title+author
                 BEFORE POST (carry N1): one identity per generation,
                 never two rows whose rec_keys differ for one book.
  control chars  every POSTed string is asserted free of C0/C1 control
                 characters (carry N5: \x1f is seed.book_key's join
                 delimiter — one in a field is door-reachable join
                 injection; the corpus is asserted at load too, a repeated
                 isbn between two books refused there — N3's input).
  kategori       nyhet|klassiker|blandad rides EVERY row (MC 12602
                 F-P4-1); the corpus `category` maps classic/new_release/
                 mix onto the door's vocabulary.
  floor          fewer than MIN_OUTPUT_ROWS accepted rows => REFUSE the
                 POST, loud, non-zero: a thin generation is a failed one.
  mix            <1 nyhet OR <1 klassiker in the accepted output =>
                 REFUSE, loud, non-zero, ZERO POSTs (owner scope — "newly
                 released books as well as classics"; one half of that is
                 not the promised generation; DA c3 FIX item 2). blandad
                 rows are welcome, never load-bearing.
  taste          zero graded rows from --library => REFUSE, loud,
                 non-zero, BEFORE the lane ask (MC 12602 scope row 2:
                 "based on the current graded library" must be REAL).
  near-miss      (MC 12617, DA c3 F-P2-2c; c10 F-DA10-1 widened the shelf
                 side to GRADED ∪ EVERY door row) a candidate that LOOKS
                 like a shelf card without joining it is an ownership
                 ambiguity the ONE identity law can never join: the WHOLE
                 generation is REFUSED before the lane ask (math and the
                 shared classifier ride in scripts/ai_rek_belt — flag
                 math and strict-key refusal semantics UNCHANGED).
  read-list      (MC 12643, owner ruling "A"; fix wave DA c10 F-P1-1)
                 EVERY door row excludes OFFER-SIDE by the ONE wish_key
                 law (counter dropped_read) AND an accent-fold lane
                 (belt.fallhyll — DROP only, counter dropped_fold, loud
                 per row; over-dropping costs a recommendation, never
                 recommends a read book), BEFORE the lane ask. An
                 unreadable, over-cap (>2 MB, >5000 rows — F-DA10-2) or
                 malformed list refuses the WHOLE pass (exit 5): an
                 UNfiltered generation is NEVER posted.
  rehearsal      (MC 12617, DA c5 F-P4-1) a live --full requires a
                 COMPLETED --dry-run of the SAME corpus vs the SAME
                 library in the same run window (the 0→1 sweep cliff —
                 refused before any network); upsert needs no stamp.
  refresh        (MC 12647, M11-N11 — owner ruling verbatim "Ai list
                 refreshes each 20 books graded") --check-refresh
                 compares the shelf's graded count against the LAST
                 ACCEPTED-wave record (scripts/ai_rek_refresh.py): delta
                 >= 20 => dry-run rehearsal + full wave in the SAME
                 invocation; delta < 20 or no record => exit 0 loud
                 NOT-due (never a surprise wave); a drift record => exit
                 2 with ZERO network. Every accepted full wave REBASES
                 the record (graded_count + accepted + ts, 0600 files in
                 $AI_REK_STATE_DIR — fleet default /home/claudecode/.
                 liselott-rek, NEVER the repo; README documents the path).

Delivery: POST {base}/ai-rek through curl_transport (ONE transport for
both door runners). The credential from env AI_REC_DOOR_TOKEN rides the
`X-Ai-Rek-Token` header through curl's PLAIN `--config <per-call 0600
tmpfile>` form — ZERO token bytes on the child's argv (MC 12616, DA c3
P2, leg-proved against a live curl child; NOT the `@` form — DA c6
F-P1-1; the wire-arrival legs live in tests/test_door_transport.py),
64-hex asserted through the door's OWN TOKEN_SHAPE, the value never
echoed. --dry-run prints the ranked JSON and POSTS NOTHING — every gate
still runs (keys, shelf, lane ask) — the demo must prove something; the
rehearsal rides the SAME join as the live run. --full (DEFAULT off, MC
12616) sends the door's full-swap envelope (server-side sweep, deleted_n
in the receipt); since MC 12617 a live --full ALSO requires the dry-run
rehearsal stamp named above; since MC 12647 a door-ACCEPTED full wave
also writes the accepted-wave record the refresh trigger measures from.
--lane-timeout (default 600 s, DA c4 P3) sizes the lane ask — the 300 s
it shipped with died mid-generation on the live DA run.

KNOWN LIMITS, documented not papered over:
  FULL-REPLACEMENT SWEEP (MC 12602 scope row 1) — CLOSED by MC 12616:
  `--full` sends the door's full-swap envelope; absent `new` rows are
  deleted door-side (state accept/decline NEVER; an empty generation is
  refused fail-loud, rows kept). The default upsert path is byte-identical
  to MC 12601.
  DECLINE-FLIP RACE (carry N2, app-side P3): unreachable from this
  single-writer lane — it needs the owner's browser flip mid-ingest.
  OWNED-BOOK TITLE SPELLINGS (live demo 2026-11-17, corrected by DA c3
  F-P2-2c): a subtitle tail cannot join the shelf's plain spelling —
  `seed.book_key` alias-resolves AUTHORS only (DA probe3), so no alias
  row repairs a title; the full corrected story, dead claims included,
  lives in the LEDGER and CORPUS.md. The repair that works is data-side:
  the shelf-exact corpus rebase (MC 12617). This runner adds NO second
  title normalizer beside the §5.3 chain — the c10 fold lane is an
  EXCLUSION (drop) view through the belt's own `_fold`, never a join.
  (The diary's own strings are named nowhere here: the exposure gate
  counts this file.)
"""
import argparse
import csv
import json
import os
import sys
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import ai_rek, onska                # THE door's vocabulary + identity
from scripts import pris_parse as pp         # THE shelf-page parser
from scripts.ai_rek_belt import (near_miss_kandidater,   # MC 12617 belts
                                 read_library_keys,       # MC 12643 keys
                                 fallhyll, falltraffar,   # c10 fold lane
                                 rehearsal_held, rehearsal_skriv)
from scripts.ai_rek_lane import (ISBN_FULL, _har_kontrolltecken,  # MC 12647
                                 LANE_TIMEOUT_S, build_prompt,     # ask +
                                 lane_ask, parse_ranking,          # answer
                                 _validera, dedupe_identitet)      # gates
from scripts.ai_rek_refresh import check_refresh, refresh_record_skriv
from scripts.curl_transport import _curl, _curl_config   # THE shared transport

ENV_URL, ENV_TOKEN = "LISELOTT_URL", ai_rek.AI_REK_TOKEN_ENV
BASE_DEFAULT = "https://sibbamala.com/liselott"
GET_TIMEOUT_S, POST_TIMEOUT_S = 15, 30
TOKEN_SHAPE = ai_rek.TOKEN_SHAPE            # the door's 64-hex shape, ONE shape

MIN_OUTPUT_ROWS = 20                        # MC 12601: output >=20 ranked rows

# The corpus.tsv's 13 columns, exactly as the N1 output ships them.
CORPUS_COLS = ["isbn13", "title", "author", "year", "why", "review_source_url",
               "review_quote", "fit_note", "category", "year_basis",
               "fetch_method", "libris_id", "citation_status"]
# The corpus' category vocabulary mapped onto the door's CHECK vocabulary
# (app.ai_rek.KATEGORIER) — one mapping, the door's values on the far side.
KATEGORI_MAP = {"new_release": "nyhet", "classic": "klassiker", "mix": "blandad"}


def read_corpus(path):
    """corpus.tsv -> (rows, None) or (None, reason). The parse pins the
    shipped shape: header == CORPUS_COLS exactly, tab rows of 13 fields;
    isbn13 exactly 13 ASCII digits and UNIQUE across rows (one isbn on
    two books = the N3 merge-lane trap, refused here — the furthest point
    from the door); year empty or an
    int in the door's 1000..2100; NO field carries a control char (N5);
    title/review_source_url non-empty (the door's shape duty at load).
    Every kept row carries its door values: kategori + wish_key."""
    rows, isbns = [], {}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter="\t")
        header = next(reader, None)
        if header != CORPUS_COLS:
            return None, "kolumnrubriker matchar inte corpus.tsv:s 13 kolumner"
        for n, f in enumerate(reader, start=2):
            if len(f) != len(CORPUS_COLS):
                return None, f"rad {n}: {len(f)} fält, förväntades 13"
            row = dict(zip(CORPUS_COLS, (x.strip() for x in f)))
            bad = [k for k, v in row.items() if _har_kontrolltecken(v)]
            if bad:
                return None, f"rad {n}: kontrolltecken i {','.join(bad)} (N5)"
            isbn = row["isbn13"]
            if not (ISBN_FULL.fullmatch(isbn) and isbn.isascii()):
                return None, f"rad {n}: isbn13 inte 13 ASCII-siffror"
            if isbn in isbns:
                return None, f"rad {n}: isbn13 dupliceras över två böcker (N3)"
            kategori = KATEGORI_MAP.get(row["category"])
            if kategori not in ai_rek.KATEGORIER:
                return None, f"rad {n}: category {row['category']!r} utanför ordet"
            year = row["year"]
            if year and not (year.isascii() and year.isdigit()
                             and 1000 <= int(year) <= 2100):
                return None, f"rad {n}: year {year!r} utanför dörrens domän"
            if not (row["title"] and row["review_source_url"]):
                return None, f"rad {n}: tom title/review_source_url"
            row["kategori"] = kategori
            row["nyckel"] = onska.wish_key(row["title"], row["author"])
            isbns[isbn] = n
            rows.append(row)
    if not rows:
        return None, "korpusen är tom"
    return rows, None


def read_library(url):
    """The PUBLIC shelf through the shared transport -> (graded cards,
    error|None). Non-200 is a hard error: a partial page is the WRONG
    library, and the taste profile built from it would be a lie."""
    status, body = _curl([url], timeout_s=GET_TIMEOUT_S)
    if status != 200:
        return None, f"bibliotek {status}"
    return pp.read_graded(body.decode("utf-8", "replace")), None


def door_post(url, token, rows, *, full=False):
    """The ONE delivery on the shared transport (posture inherited from
    the retired pris runner, MC 12606): JSON on stdin via --data-binary
    @-, the token on `X-Ai-Rek-Token`, one try then loud, (status,
    body-bytes) back. `full=True` wraps the door's full-swap envelope."""
    payload = {"generation": rows} if full else rows
    return _curl_config(
        [("X-Ai-Rek-Token", token)],        # MC 12616: the secret rides a
        lambda config: ["--request", "POST",  # per-call 0600 --config file,
                        "--header",            # NEVER argv (DA c3 P2, the
                        "Content-Type: application/json",  # /proc/<curl> leak)
                        "--config", config,
                        "--data-binary", "@-", url],
        timeout_s=POST_TIMEOUT_S,
        stdin_data=json.dumps(payload).encode("utf-8"))


def run_pass(corpus_path, library_url, base, *, dry_run=False,
             get_library=read_library, get_keys=read_library_keys,
             lane=lane_ask, post=door_post,
             say=None, full=False):
    """One generation end-to-end; returns the exit code. Every external
    touch is an injectable seam (MC 12547's shape): the whole contract
    tests with zero network. Exit: 0 ok; 2 input/config refused; 3 lane
    answer refused; 4 floor not met; 5 door refused — the read-title
    door's unreadable OR OVER-CAP list included (MC 12643 + c10
    F-DA10-2: an unfiltered generation is never posted); 6 mix owed.
    `full=True` (CLI `--full`, DEFAULT off) rides the door's full-swap
    envelope — every gate IDENTICAL, only the delivery mode changes; the
    validated rows ARE the complete new generation the door sweeps. A
    DOOR-ACCEPTED full wave also rebases the accepted-wave record (MC
    12647: graded_count + accepted + ts — the refresh baseline)."""
    say = say or (lambda line: print(line, flush=True))

    rows, fel = read_corpus(corpus_path)
    if rows is None:
        say(f"ALARM korpus avvisad: {fel} — noll POST")
        return 2
    if full and not dry_run:
        # MC 12617 (DA c5 F-P4-1): the sweep mode never runs un-rehearsed.
        # Checked FIRST, before the shelf read and the lane ask — a refused
        # --full must cost nothing but the refusal.
        held, anledning = rehearsal_held(base, library_url, corpus_path)
        if not held:
            say(f"ALARM --full vägras: {anledning} — kräver fullbordad "
                "--dry-run i samma körningsfönster (N8b) — noll POST")
            return 2
    token = os.environ.get(ENV_TOKEN) or ""
    if not TOKEN_SHAPE.fullmatch(token):      # the env NAME is named, the
        say(f"ALARM {ENV_TOKEN} saknas eller har fel form (64 hex) "
            "— vägrar POST")                  # VALUE is never echoed
        return 2
    # MC 12643 (owner ruling "A"): the COMPLETE read-title list rides the
    # SAME door on the SAME token, read FIRST — before the shelf read and
    # the lane ask. An unreadable list costs the refusal and nothing else;
    # a --dry-run now rehearses over the SAME join as the live run (a
    # malformed env refuses at the check above, before any door touch).
    nycklar, fel = get_keys(f"{base}/ai-rek/library-keys", token)
    if nycklar is None:
        say(f"ALARM läsnycklar avvisade: {fel} — fail-closed: EN OUTFILTRERAD "
            "generation POSTAS ALDRIG — noll POST, ingen lane-ask")
        return 5
    graded, fel = get_library(library_url)
    if graded is None:
        say(f"ALARM bibliotek avvisat: {fel} — noll POST")
        return 2
    if not graded:                            # MC 12602 scope row 2: the
        say("ALARM smakprofil tom: biblioteket gav noll betygssatta rader "
            "— vägrar POST (ingen 'baserat på hyllan' utan hyllan)")
        return 2                              # refuse BEFORE the lane ask

    agda_nycklar = {onska.wish_key(c["title"], c["author"]) for c in graded}
    agda_isbn = {c["isbn13"] for c in graded if c.get("isbn13")}
    # MC 12643 (owner ruling "A"): EVERY bok row the door answered — read
    # AND wishlist — keyed by THE SAME wish_key law `_samma_bock` uses, so
    # a book she owns is invisible to the lane, not just to the POST.
    lästa = {onska.wish_key(n["titel"], n.get("forfattare") or "")
             for n in nycklar}
    fall_hyll = fallhyll(nycklar)            # c10 F-P1-1: the accent-fold lane
    kandidater = [r for r in rows
                  if r["nyckel"] not in agda_nycklar
                  and r["isbn13"] not in agda_isbn]
    före_läs = len(kandidater)
    kvar, fold_bort = [], []
    for r in kandidater:                 # strict first; survivors may fold
        if r["nyckel"] in lästa:
            continue
        (fold_bort if falltraffar(r, fall_hyll) else kvar).append(r)
    kandidater = kvar
    dropped_read = före_läs - len(kvar) - len(fold_bort)
    for r in fold_bort:                  # loud per row, then counted
        say(f"REK dropped_fold: {r['title']} — {r['author']} — accent-folds "
            "onto a bok row (dropped, never offered — c10 F-P1-1)")
    # F-C3-1 (DA c3 item 3, the tester's L11): the accepted set IS the
    # OFFERED set — an isbn naming a corpus row the join DROPPED as owned
    # is refused post-parse even when the model names it back (the belt
    # runs after the prompt was already clean; the prompt is intent, this
    # is the guarantee).
    by_isbn = {r["isbn13"]: r for r in kandidater}
    agnas_isbn = {r["isbn13"] for r in rows if r["isbn13"] not in by_isbn}
    say(f"REK korpus={len(rows)} drogs_bort={len(rows) - före_läs} "
        f"dropped_read={dropped_read} dropped_fold={len(fold_bort)} "
        f"läsnycklar={len(nycklar)} kandidater={len(kandidater)} "
        f"betygssatta={len(graded)}")
    if not kandidater:
        say("ALARM alla kandidater finns redan på hyllan — noll POST")
        return 2
    # c10 F-DA10-1: the belt's shelf side is the GRADED cards AND every
    # door row (a near-miss against a read-but-unrated card is the same
    # ownership ambiguity); the classifier's math is untouched.
    hyllkort = {(c["title"], c["author"]) for c in graded} | {
        (n["titel"], n.get("forfattare") or "") for n in nycklar}
    near_miss = near_miss_kandidater(
        kandidater, [{"title": t, "author": a} for t, a in sorted(hyllkort)])
    if near_miss:
        # MC 12617 (DA c3 F-P2-2c): a candidate that LOOKS like a graded
        # card but cannot join is an ownership ambiguity the ONE identity
        # mechanism can never resolve (aliases are authors-only) — the
        # generation is refused, counts only in the line (the delivery
        # posture: corpus titles never ride stdout), the data lane rebases.
        say(f"ALARM near-miss mot hyllan: {len(near_miss)} kandidater "
            "liknar hyllkort (graderade ELLER läslistade) utan att joina — "
            "vägrar generation (0 near-miss krävs, N8b; kör om "
            "korpus-rebasen) — noll POST")
        return 2

    try:
        ranking = parse_ranking(lane(build_prompt(graded, kandidater)))
    except (ValueError, KeyError, urllib.error.URLError, OSError) as e:
        say(f"ALARM lane-svar avvisas: {type(e).__name__}: {e} — noll POST")
        return 3
    godkanda = dedupe_identitet(
        _validera(ranking, by_isbn, agnas_isbn, say=say), say=say)
    say(f"REK godkanda={len(godkanda)} av {len(ranking)} poster "
        f"(golv {MIN_OUTPUT_ROWS})")
    if len(godkanda) < MIN_OUTPUT_ROWS:       # thin generation = failed one
        say(f"ALARM för tunn generation: {len(godkanda)} < {MIN_OUTPUT_ROWS} "
            "rader — vägrar POST")
        return 4
    kategorier = {p["kategori"] for p in godkanda}
    if not {"nyhet", "klassiker"} <= kategorier:      # owner scope: "newly
        saknade = sorted({"nyhet", "klassiker"} - kategorier)   # released
        say(f"ALARM blandningsvillkor: output saknar {','.join(saknade)} "
            "— minst en nyhet OCH en klassiker krävs, vägrar POST")        # books
        return 6                              # as well as classics
    if dry_run:                               # prints; the ONLY skipped POST
        # MC 12617: this return-0 IS the completed rehearsal — the stamp
        # (corpus sha + library + counts, no secrets) is what authorizes
        # one --full run in the same window. Every gate above passed, so a
        # refused rehearsal can never leave a stamp. MC 12647 adds the
        # shelf size the rehearsal SAW (graded_count) to the same stamp.
        rehearsal_skriv(base, library_url, corpus_path,
                        accepted=len(godkanda), kategorier=kategorier,
                        graded_count=len(graded))
        say("DRY-RUN-RADER " + json.dumps(godkanda, ensure_ascii=False))
        say(f"DRY-RUN: {len(godkanda)} rankade rader utskrivna, INGET POSTAT")
        return 0

    if full:
        # Belt before the byte: the corpus may have changed since the
        # window check above (the lane ask takes minutes) — re-hash.
        held, anledning = rehearsal_held(base, library_url, corpus_path)
        if not held:
            say(f"ALARM --full vägras vid leveransen: {anledning} "
                "— noll POST")
            return 2
    status, body = post(f"{base}/ai-rek", token, godkanda, full=full)
    if not 200 <= status < 300:
        say(f"ALARM dörren svarade {status}: {body[:200]!r} — generationen "
            "landade inte")
        return 5
    say(f"REK POST OK status={status} "
        f"kvittering={body.decode('utf-8', 'replace')[:200]}")
    if full:                                  # MC 12647 (M11-N11): the
        refresh_record_skriv(base, library_url,   # accepted full wave IS the
                             graded_count=len(graded),  # refresh baseline —
                             accepted=len(godkanda))    # tick reads it back
        say(f"REK REFRESH-BASLINJE: {len(graded)} betygssatta vid accepterad "
            "full våg — nästa våg vid +20 (scripts/ai_rek_refresh.py)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--library", default=None,
                    help="public shelf URL (default $LISELOTT_URL/bibliotek, "
                         f"else {BASE_DEFAULT}/bibliotek)")
    ap.add_argument("--corpus", required=True, help="corpus.tsv path")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the ranked rows; POST nothing")
    ap.add_argument("--full", action="store_true",
                    help="MC 12616: POST the rows as the COMPLETE new "
                         "generation (full-swap envelope) — the door "
                         "deletes state='new' rows absent from it; DEFAULT "
                         "off = today's plain upsert")
    ap.add_argument("--check-refresh", action="store_true",
                    help="MC 12647 (M11-N11, owner ruling 'Ai list "
                         "refreshes each 20 books graded'): compare the "
                         "public shelf's graded count against the LAST "
                         "ACCEPTED-wave record; delta >= 20 => dry-run "
                         "rehearsal + full wave in THIS invocation; else "
                         "exit 0 loud not-due (never a surprise wave)")
    ap.add_argument("--lane-timeout", type=int, default=LANE_TIMEOUT_S,
                    help=f"Lane E ask budget in seconds (default "
                         f"{LANE_TIMEOUT_S}; the shipped 300 died mid-"
                         "generation, DA c4 P3)")
    args = ap.parse_args(argv)
    base = (os.environ.get(ENV_URL) or BASE_DEFAULT).rstrip("/")
    library = args.library or f"{base}/bibliotek"
    if args.check_refresh:
        return check_refresh(
            args.corpus, library, base, run_pass=run_pass,
            get_library=read_library,
            lane=lambda prompt: lane_ask(prompt,
                                         timeout_s=args.lane_timeout))
    return run_pass(args.corpus, library, base, dry_run=args.dry_run,
                    full=args.full,
                    lane=lambda prompt: lane_ask(prompt,
                                                 timeout_s=args.lane_timeout))


if __name__ == "__main__":
    raise SystemExit(main())
