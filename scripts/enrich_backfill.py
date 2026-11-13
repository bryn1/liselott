#!/usr/bin/env python3
"""Enrichment backfill (§10/T3.5) — the ONLY place in this project that calls
the providers in a loop. Flags are EXACTLY the plan's: --dry-run --limit N
--offline --authors --report PATH. There is NO --only-missing flag (P2-b): the
DEFAULT scope already is "rows missing isbn/cover", so a re-run resumes by
itself — which is how the F-2 convergence loop runs (plain re-run, no flags
invented, until two consecutive full passes add covers_stored == 0).

Scope:  SELECT id FROM book WHERE isbn13 IS NULL OR cover_path IS NULL
        ORDER BY id  [LIMIT n]
Pacing: one PACE_S (1.0 s) pause before EVERY provider call (§12 courtesy).
Report: --report PATH wins (P2-f); else state_base()/enrich_report.json.

--offline runs the WHOLE pipeline against a scratch COPY of the DB inside a
scratch state dir ($LISELOTT_DATA_DIR swapped for the duration), so a rehearsal
cannot poison a real row or drop a fake cover file into the real covers/ — the
code path is the live one, the target is not, and the report says
writes=0. --dry-run consults nothing at all and lists the planned ids.
--authors belongs to the candidate pool, which is T6.3's build; it refuses
loudly rather than quietly doing nothing (the P2-b defect class)."""
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

from app import db, enrich  # noqa: E402

PACE_S = 1.0                       # §12: 1 req/s against the providers
SCOPE_WHERE = "isbn13 IS NULL OR cover_path IS NULL"


def scope_ids(conn, limit=None):
    sql = f"SELECT id FROM book WHERE {SCOPE_WHERE} ORDER BY id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return [r[0] for r in conn.execute(sql)]


def paced_fetch(fetch, pace):
    """A cover image is an outbound request too — the 1 req/s courtesy covers
    it, not just the search calls."""
    def call(url, **kw):
        pace(PACE_S)
        return fetch(url, **kw)
    return call


def paced(transports, pace):
    """1 req/s wrapped around every CONSULTED provider call (a provider the
    transport skips with None is not asked, so it never costs a pause)."""
    wrapped = {}
    for name, transport in transports.items():
        if transport is None:
            wrapped[name] = None
            continue

        def call(title, authors, _t=transport):
            pace(PACE_S)
            return _t(title, authors)

        wrapped[name] = call
    return wrapped


def run_pass(conn, ids, transports, fetch, pace, persist=True):
    # isbn_resolved counts isbn13 values WRITTEN (the DoD's floor metric: what
    # the diary GAINED), matched counts provider hits that passed the policy —
    # conflating them made a re-run report "54 resolved" while writing nothing.
    report = {"scanned": 0, "processed": 0, "matched": 0, "isbn_resolved": 0,
              "covers_stored": 0, "genres_set": 0, "failures": 0, "writes": 0,
              # per-lane attribution (owner ruling 2026-11-13): a missed floor
              # must name which provider missed it
              "by_source": {lane: {"matched": 0, "isbn": 0, "covers": 0,
                                   "genres": 0}
                            for lane in ("libris", "openlibrary", "googlebooks")}}
    for book_id in ids:
        report["scanned"] += 1
        outcome = enrich.resolve_book(conn, book_id, transports=transports,
                                      fetch=fetch)
        report["processed"] += 1
        if not outcome.get("resolved"):
            report["failures"] += 1
            continue
        report["matched"] += 1
        lane = report["by_source"].setdefault(
            outcome.get("source") or "unknown",
            {"matched": 0, "isbn": 0, "covers": 0, "genres": 0})
        lane["matched"] += 1
        if outcome.get("isbn_written"):
            report["isbn_resolved"] += 1
            lane["isbn"] += 1
        if outcome.get("cover"):
            report["covers_stored"] += 1
            lane["covers"] += 1
        if outcome.get("genres_written"):
            report["genres_set"] += 1
            lane["genres"] += 1
        if persist:
            report["writes"] += 1
    return report


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


def main(argv=None, transports=None, fetch=None, pace=None):
    ap = argparse.ArgumentParser(description="Anrikna bokhyllan (ISBN/år/genre/omslag).")
    ap.add_argument("--dry-run", action="store_true",
                    help="visa vad som SKulle göras — gör ingenting")
    ap.add_argument("--limit", type=int, default=None, help="max antal rader den här omgången")
    ap.add_argument("--offline", action="store_true",
                    help="rör inga nätverk och inga riktiga rader: kör mot en kopia")
    ap.add_argument("--authors", action="store_true",
                    help="kandidatpoolen — byggs i T6.3, vägrar här")
    ap.add_argument("--report", default=None,
                    help="vart reportet skrivs (default: state_base()/enrich_report.json)")
    args = ap.parse_args(argv)

    if args.authors:
        print("FAIL: --authors (kandidatpoolen) byggs i T6.3 — den här versionen "
              "vägrar hitta på den i hemlighet (§14 T3.5, P2-b).", file=sys.stderr)
        return 2

    report_path = Path(args.report) if args.report else db.state_base() / "enrich_report.json"
    pace = pace or time.sleep
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
