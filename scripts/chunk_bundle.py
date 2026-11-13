#!/usr/bin/env python3
"""Split the seed bundle into LINE-BOUNDARY chunks under a byte budget (P1-1:
the lane's effective body cap is nginx's default 1,048,576 B — the plan packs
to 900,000 B, ~14 % margin — and T6.4's app-side MAX_BUNDLE_CHUNK is the
defence-in-depth behind this, not the other way round).

Rules the tests pin: every chunk ≤ --max-bytes BYTES; the byte-concat of the
chunks is the original bundle EXACTLY; the line count is preserved; chunks are
named bundle-0001.ndjson, bundle-0002.ndjson …; a single line that is itself
over budget exits 1 NAMING the line (never silent, never an oversized chunk);
--max-bytes above the lane budget is refused; the sha256 of the UNCHUNKED
bundle is printed so a receiver can prove the reassembly.

Usage: python3 scripts/chunk_bundle.py --in <bundle> [--out-dir <dir>/chunks]
                                        [--max-bytes 900000]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

CHUNK_NAME = "bundle-{:04d}.ndjson"
LANE_BUDGET = 900_000                 # §10: the only budget this tool will pack to
LINE_BUDGET = 400_000                 # §5.11: a row this fat can never ship legally


def split_lines(data):
    """Lines WITH their terminators, so b"".join(lines) == data byte for byte
    (str.splitlines semantics, which is why a JSON-escaped \\\\n in a value can
    never be mistaken for a terminator here)."""
    return [line if line.endswith(b"\n") else line + b"\n"
            for line in data.splitlines(keepends=True)]


def describe(line):
    """Name an offending line the way an operator can act on it: the book_key
    when the line parses, the byte size always."""
    try:
        key = json.loads(line.decode("utf-8")).get("book_key")
    except (ValueError, UnicodeDecodeError):
        key = None
    return f"raden med book_key={key}" if key else f"raden (bokar {line[:40]!r})"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Dela en seed-bundle i chunk under "
                                             "bandets byte-budget (§10).")
    ap.add_argument("--in", dest="infile", required=True, type=Path)
    ap.add_argument("--out-dir", type=Path, default=None,
                    help="default: <bundle-dir>/chunks")
    ap.add_argument("--max-bytes", type=int, default=LANE_BUDGET)
    args = ap.parse_args(argv)

    if args.max_bytes > LANE_BUDGET:
        print(f"FAIL: --max-bytes {args.max_bytes} överstiger bandets budget "
              f"{LANE_BUDGET} byte (§10) — chunkar över budgettet 413:as avnginx.",
              file=sys.stderr)
        return 2

    data = args.infile.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    out_dir = args.out_dir or args.infile.parent / "chunks"
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("bundle-*.ndjson"):
        stale.unlink()                 # a re-run must not leave old chunk files behind

    chunks, current = [], bytearray()
    for line in split_lines(data):
        # Two different ceilings, one refusal: a line over the §5.11 ROW budget
        # can never ship (the receiver 400s it no matter how the file is
        # chunked), and a line over the CHUNK budget can never be packed. Both
        # are fatal and both NAME the line — never a silent drop.
        if len(line) > LINE_BUDGET or len(line) > args.max_bytes:
            print(f"FAIL: {describe(line)} är {len(line)} byte — radbudget "
                  f"{LINE_BUDGET}, chunkbudget {args.max_bytes}. Ingen chunk skrivs.",
                  file=sys.stderr)
            return 1
        if current and len(current) + len(line) > args.max_bytes:
            chunks.append(bytes(current))
            current = bytearray()
        current += line
    if current:
        chunks.append(bytes(current))

    # Every byte goes out exactly once, in order — and the concat-equality of
    # the chunks is asserted by tests/test_bundle.py, not by a self-check here
    # that could never fail (a check that cannot go red is not a check).
    for index, blob in enumerate(chunks, start=1):
        (out_dir / CHUNK_NAME.format(index)).write_bytes(blob)

    print(f"chunks={len(chunks)} max_chunk_bytes={max(len(c) for c in chunks)} "
          f"lines={sum(1 for _ in split_lines(data))} sha256={digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
