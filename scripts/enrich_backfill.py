#!/usr/bin/env python3
"""Enrichment backfill (§10/T3.5) — the ONLY place in this project that calls
the providers in a loop. Flags are EXACTLY the plan's: --dry-run --limit N
--offline --authors --report PATH. There is NO --only-missing flag (P2-b): the
DEFAULT scope already is "rows missing isbn/cover", so a re-run resumes by
itself — which is how the F-2 convergence loop runs (plain re-run, no flags
invented, until two consecutive full passes add covers_stored == 0).

Covers scope: SELECT id FROM book WHERE isbn13 IS NULL OR cover_path IS NULL
        ORDER BY id  [LIMIT n]
Pacing:   one PACE_S (1.0 s) pause before EVERY provider call (§12 courtesy).
Report:   --report PATH wins (P2-f); else state_base()/enrich_report.json.

--offline runs the WHOLE pipeline against a scratch COPY of the DB inside a
scratch state dir ($LISELOTT_DATA_DIR swapped for the duration), so a rehearsal
cannot poison a real row or drop a fake cover file into the real covers/ — the
code path is the live one, the target is not, and the report says
writes=0. --dry-run consults nothing at all and lists the planned ids.

--authors (T6.3) is the candidate pool: it runs enrich_loop.candidates_pass —
the SAME function POST /backfill?mode=candidates drives (P2-d, one mechanism).
§8's rules live in the shared core (top 10 per author, 90-day freshness, the
dedupe); this CLI adds only the batch shape: --limit bounds the authors
EXAMINED this pass, and without a limit the scan walks the whole queue while
at most MAX_AUTHORS_PER_PASS (40, §8) are ASKED — the next plain re-run
resumes where the freshness rule left off, the P2-b posture of the covers
loop. --offline refuses --authors loudly: the pool IS a network fetch, and a
flag that quietly did nothing is the P2-b defect class."""
import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import db, enrich, enrich_ol, seed  # noqa: E402
# The pacing helpers MOVED to app/enrich_loop.py when the app's own doors
# (add / omslag / backfill route) became their second caller — this CLI
# imports the mechanism, it does not own a twin (P2-d one-mechanism rule).
# T6.3 adds the candidates trio for the same reason: the CLI --authors and
# POST /backfill?mode=candidates run THE SAME builder.
from app.enrich_loop import (  # noqa: E402
    MAX_AUTHORS_PER_PASS, PACE_S, author_queue, candidates_pass,
    candidates_window, fresh_candidate, paced, paced_fetch, paced_search,
    run_pass, scope_ids)

ol_author_search = enrich_ol.author_search   # bound: the fixture seam,
                                             # same pattern as app/backfill


def scratch_pass(ids, transports, fetch, pace):
    """--offline: the real pipeline against a COPY of the DB in a scratch state
    dir; the real DB and the real covers/ are never opened for writing."""
    real_db = db.state_base() / db.DB_NAME
    scratch = Path(tempfile.mkdtemp(prefix="liselott-offline-"))
    prev_env = os.environ.get("LISELOTT_DATA_DIR")
    try:
        if real_db.exists():
            with sqlite3.connect(real_db) as src, sqlite3.connect(scratch / db.DB_NAME) as dst:
                src.backup(dst)
        conn = sqlite3.connect(scratch / db.DB_NAME)
        db.init_db(conn)
        os.environ["LISELOTT_DATA_DIR"] = str(scratch)
        try:
            return run_pass(conn, ids, transports, fetch, pace, persist=False)
        finally:
            conn.close()
            if prev_env is None:
                os.environ.pop("LISELOTT_DATA_DIR", None)
            else:
                os.environ["LISELOTT_DATA_DIR"] = prev_env
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def authors_pass(args, report_path, pace, author_search=None):
    """--authors: THE candidate builder pass (T6.3) — candidates_pass is
    enrich_loop's, shared with POST /backfill?mode=candidates line for line.
    --limit bounds the authors EXAMINED this pass; the scan without a limit
    walks the whole diary-author queue while at most MAX_AUTHORS_PER_PASS
    (40, §8) are ASKED. Fresh authors are skipped by the 90-day rule, so the
    next plain re-run resumes on the authors still owed — resume by itself,
    no cursor flags invented (P2-b, same posture as the covers loop).
    --dry-run lists the planned author ids and asks NOTHING."""
    search = author_search if author_search is not None else ol_author_search
    now, stale_before = candidates_window()
    aliases = seed.app_aliases()
    with sqlite3.connect(db.state_base() / db.DB_NAME) as conn:
        db.init_db(conn)
        queue_all = author_queue(conn)
        batch = author_queue(conn, args.limit)
        report = {"mode": "candidates", "total": len(queue_all),
                  "dry_run": bool(args.dry_run), "limit": args.limit,
                  "pace_s": PACE_S}
        if args.dry_run:
            planned = [aid for aid, name in batch
                       if not fresh_candidate(
                           conn, aliases.get(name, name), stale_before)]
            report.update({"scanned": len(batch), "processed": len(batch),
                           "fetched": 0, "failures": 0,
                           "new_candidates": 0,
                           "planned": planned[:MAX_AUTHORS_PER_PASS]})
        else:
            report.update(candidates_pass(
                conn, batch, paced_search(search, pace),
                now=now, stale_before=stale_before, aliases=aliases,
                max_fetch=MAX_AUTHORS_PER_PASS))
        report["candidate_total"] = conn.execute(
            "SELECT COUNT(*) FROM candidate").fetchone()[0]
        print(" ".join(f"{k}={report[k]}" for k in
                       ("mode", "total", "dry_run", "scanned", "processed",
                        "fetched", "failures", "new_candidates",
                        "candidate_total")))
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    return 0


def main(argv=None, transports=None, fetch=None, pace=None,
         author_search=None):
    ap = argparse.ArgumentParser(description="Anrikna bokhyllan (ISBN/år/genre/omslag).")
    ap.add_argument("--dry-run", action="store_true",
                    help="visa vad som SKulle göras — gör ingenting")
    ap.add_argument("--limit", type=int, default=None, help="max antal rader den här omgången")
    ap.add_argument("--offline", action="store_true",
                    help="rör inga nätverk och inga riktiga rader: kör mot en kopia")
    ap.add_argument("--authors", action="store_true",
                    help="kandidatpoolen — författarsök per författare "
                         "(delad byggare med POST /backfill?mode=candidates)")
    ap.add_argument("--report", default=None,
                    help="vart reportet skrivs (default: state_base()/enrich_report.json)")
    args = ap.parse_args(argv)

    if args.authors and args.offline:
        print("FAIL: --offline gäller inte --authors — kandidatpoolen är en "
              "verklig nätförfrågan; öva med --dry-run i stället "
              "(P2-b: flaggan vägrar, den hittar inte på i tysthet).",
              file=sys.stderr)
        return 2

    report_path = Path(args.report) if args.report else db.state_base() / "enrich_report.json"
    pace = pace or time.sleep

    if args.authors:
        return authors_pass(args, report_path, pace, author_search)

    with sqlite3.connect(db.state_base() / db.DB_NAME) as conn:
        db.init_db(conn)
        # total = everything still missing (the F-2 loop watches THIS number,
        # not the batch size); ids = the batch this pass will take.
        report = {"total": len(scope_ids(conn)), "dry_run": bool(args.dry_run),
                  "offline": bool(args.offline), "pace_s": PACE_S,
                  "limit": args.limit}
        ids = scope_ids(conn, args.limit)

        if args.dry_run:
            report.update({"scanned": 0, "processed": 0, "matched": 0,
                           "isbn_resolved": 0, "covers_stored": 0, "genres_set": 0,
                           "failures": 0, "writes": 0, "by_source": {},
                           "planned": ids})
        else:
            if transports is not None:
                wired = transports
            elif args.offline:
                wired = {name: None for name in enrich.PROVIDER_ORDER}
            else:
                wired = enrich.live_transports(conn)
            fetch = paced_fetch(fetch or enrich.http_get, pace)
            if args.offline:
                report.update(scratch_pass(ids, paced(wired, pace), fetch, pace))
            else:
                report.update(run_pass(conn, ids, paced(wired, pace), fetch, pace))

        print(" ".join(f"{k}={report[k]}" for k in
                       ("total", "scanned", "processed", "matched", "isbn_resolved",
                        "covers_stored", "genres_set", "failures", "writes",
                        "by_source")))
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
