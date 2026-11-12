#!/usr/bin/env python3
"""Seed importer CLI (§5.9) — a thin caller over app/seed.load(), the SAME
functions the HTTP routes use later (one mechanism). Exit 0 only if the
counts match the audited outcome; a validator-flagged row (or count drift)
exits nonzero and names the row — the importer refuses a silent drift."""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import db, seed  # noqa: E402

AUDITED = {"parsed": 725, "stored": 724, "duplicates": 1,
           "ratings": 6, "ljudbok": 52}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", help="target DB path (default: state_base()/liselott.db)")
    ap.add_argument("--raw", default=str(ROOT / "data-import/seed-books-raw.md"))
    ap.add_argument("--aliases", default=str(ROOT / "data-import/author_aliases.csv"))
    ap.add_argument("--overrides", default=str(ROOT / "data-import/import_overrides.csv"))
    args = ap.parse_args(argv)

    if args.db:
        target = Path(args.db)
        target.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(target)
        report_dir = target.parent
    else:
        conn = db.connect()
        report_dir = db.state_base()
    db.init_db(conn)
    report = seed.load(conn, args.raw, args.aliases, args.overrides)
    conn.close()

    (report_dir / "import_report.json").write_text(
        json.dumps({**report, "duplicates": report["duplicates_pairs"]},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    if report["flagged"]:
        for title in report["flagged"]:
            print(f"FAIL validator (§5.4): rad med trasig författare: {title}",
                  file=sys.stderr)
        return 2
    counts = {k: report[k] for k in AUDITED}
    print(json.dumps(counts, ensure_ascii=False))
    if counts != AUDITED:
        print(f"FAIL: counts {counts} differ from audited {AUDITED} (§5.9)",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
