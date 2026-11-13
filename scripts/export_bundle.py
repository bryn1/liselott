#!/usr/bin/env python3
"""Export the enriched build DB as the seed bundle (§5.11 keys, F-1 export:
enrichment happens HERE, on the VM350 build DB, and travels to production as
data — production never calls the providers).

One JSON line per stored book, EXACTLY the §5.11 keys, and every line within
the 400 000-byte §5.11 budget — a fatter row exits 1 NAMING the row instead of
shipping a bundle the lane would choke on. `cover_b64` is the base64 of the
stored ≤340×510 JPEG (the SAME bytes store_cover wrote; no second image
pipeline), null when the book has no cover.

Usage: LISELOTT_DATA_DIR=/home/claudecode/liselott-build \\
         python3 scripts/export_bundle.py --out /home/claudecode/liselott-bundle/seed-bundle.jsonl
"""
import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import db  # noqa: E402

LINE_BUDGET = 400_000                 # §5.11: the per-row transport budget

BOOKS_SQL = """
SELECT b.id, b.book_key, b.title, b.date_read, b.read_year, b.format, b.rating,
       b.status, b.isbn13, b.isbn10, b.year, b.cover_path, b.cover_source,
       (SELECT group_concat(a.name, char(9))
          FROM book_author ba JOIN author a ON a.id = ba.author_id
         WHERE ba.book_id = b.id ORDER BY a.name) AS authors,
       (SELECT group_concat(g.name, char(9))
          FROM book_genre bg JOIN genre g ON g.id = bg.genre_id
         WHERE bg.book_id = b.id ORDER BY g.name) AS genres
  FROM book b ORDER BY b.id
"""


def bundle_rows(conn, state_dir):
    """The §5.11 payload per row. A cover_path whose file is missing exports
    cover_b64=null AND cover_source=null — the importer must never be told a
    cover exists when no bytes came along."""
    for row in conn.execute(BOOKS_SQL):
        (book_id, book_key, title, date_read, read_year, fmt, rating, status,
         isbn13, isbn10, year, cover_path, cover_source, authors, genres) = row
        cover_b64 = None
        if cover_path:
            try:
                cover_b64 = base64.b64encode((state_dir / cover_path).read_bytes()).decode()
            except OSError:
                print(f"VARNING: omslagsfil saknas för {book_key} ({cover_path}) — "
                      "exporteras utan omslag", file=sys.stderr)
        if cover_b64 is None:
            cover_source = None
        yield {
            "book_key": book_key, "title": title,
            "authors": (authors or "").split("\t") if authors else [],
            "date_read": date_read, "read_year": read_year, "format": fmt,
            "rating": rating, "status": status, "isbn13": isbn13, "isbn10": isbn10,
            "year": year, "genres": (genres or "").split("\t") if genres else [],
            "cover_b64": cover_b64, "cover_source": cover_source,
        }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Exportera den anrikade byggdatabasen "
                                             "som en seed-bundle (§5.11).")
    ap.add_argument("--out", default=str(db.state_base() / "seed-bundle.jsonl"),
                    help="vart bundle-filen skrivs")
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    state_dir = db.state_base()
    rows = covers = 0
    sha = hashlib.sha256()
    with db.connect() as conn, out.open("w", encoding="utf-8") as fh:
        for payload in bundle_rows(conn, state_dir):
            line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            raw = line.encode("utf-8")
            if len(raw) > LINE_BUDGET:
                print(f"FAIL: raden för {payload['book_key']} är {len(raw)} byte — "
                      f"budget är {LINE_BUDGET} (§5.11). Bundle skrivs EJ.",
                      file=sys.stderr)
                return 1
            fh.write(line + "\n")
            sha.update(raw + b"\n")
            rows += 1
            covers += payload["cover_b64"] is not None

    print(f"rows={rows} covers={covers} bytes={out.stat().st_size}")
    print(sha.hexdigest())                      # the unchunked bundle's digest
    return 0


if __name__ == "__main__":
    sys.exit(main())
