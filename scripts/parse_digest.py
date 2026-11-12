#!/usr/bin/env python3
"""Whole-corpus DRIFT GATE (T1.7, P0-1 re-scope): parses the raw seed md with
app/seed.py and prints ONLY a sha256 digest over every parsed row plus
aggregate counts — zero diary bytes on stdout, so the gate is committable
while the corpus stays gitignored. Any field change in any of the 725 rows
flips the digest."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import seed  # noqa: E402


def parsed_tuples(raw_path):
    rows = []
    for e in seed.parse_file(raw_path):
        p = seed.parse_row(e["raw"])
        rows.append((f"{e['kind']}:{e['year']}", e["raw"], p["title"],
                     list(p["authors"]), p["date_read"], p["rating"]))
    return rows


def digest(raw_path) -> dict:
    rows = parsed_tuples(raw_path)
    payload = json.dumps(sorted(map(tuple, rows)), ensure_ascii=False)
    sections = {}
    for section, *_ in rows:
        sections[section] = sections.get(section, 0) + 1
    return {"sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            "entries": len(rows),
            "sections": sections,
            "with_date": sum(1 for r in rows if r[4] is not None),
            "with_rating": sum(1 for r in rows if r[5] is not None),
            "ljudbok": sum(1 for k, *_ in rows if k.startswith("lyssnad:"))}


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data-import/seed-books-raw.md")
    print(json.dumps(digest(raw), ensure_ascii=False, sort_keys=True))
