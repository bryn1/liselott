#!/usr/bin/env python3
"""MC 12523 — the public-repo EXPOSURE GATE: how many tracked files still
carry ≥1 real diary string?

Reads the two personal lists OUTSIDE the repo (never committed, never
printed): LISELOTT_REAL_TITLES (default /home/claudecode/liselott-data/
real-titles.txt — one whole book title per line) and LISELOTT_REAL_ISBNS
(default .../real-isbns.txt — one ISBN-13 per line, hyphen-stripped). Over
the whole tracked universe it runs `git grep -F -w -f <list>` (fixed strings,
WHOLE WORDS) and prints exactly ONE number: the count of tracked files that
hold ≥1 hit. Exit 0 only when that number is 0.

WHOLE WORDS (-w), not bare substrings: the diary holds short real titles that
are word-shape artifacts inside ordinary repo words — one four-letter diary
title is a substring of the robots.txt directive "Disallow", which no code
edit can remove (the title is named here as a CLASS, never as the word: this
script greps for these lists, so it must never carry one itself — its own
first red run, on its own docstring, is in the landing transcript). A real
title with internal spaces still matches in full, word-bounded. This is the
instrument the README's historical "36 files at 97911ce" count prefigures,
re-measured with the artifact class removed.

Red-proof duty (fleet rule: a gate that never went red is not a gate): the
landing transcript .audits/20261114-mc12523/planted-red.md shows this script
going RED on a throwaway archive-export repo holding one planted real-title
file, then GREEN with it removed — the real tree was never touched.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_HOME = Path("/home/claudecode/liselott-data")


def real_lists():
    out = []
    for var, default in (("LISELOTT_REAL_TITLES", DATA_HOME / "real-titles.txt"),
                         ("LISELOTT_REAL_ISBNS", DATA_HOME / "real-isbns.txt")):
        path = Path(os.environ.get(var, str(default)))
        lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
                 if ln.strip()]
        if not lines:
            sys.exit(f"{var} names no entries ({path}) — the gate must not "
                     "vacuously pass")
        out.append(path)
    return out


def hit_files(list_path):
    """Tracked files with ≥1 whole-word fixed-string hit for one list."""
    proc = subprocess.run(
        ["git", "grep", "-l", "-F", "-w", "-f", str(list_path), "--"],
        cwd=ROOT, capture_output=True, text=True)
    if proc.returncode not in (0, 1):           # 1 = no matches, an OK answer
        sys.exit(f"git grep failed ({proc.returncode}): {proc.stderr}")
    return set(proc.stdout.split())


def main() -> int:
    titles_path, isbns_path = real_lists()
    hits = hit_files(titles_path) | hit_files(isbns_path)
    print(len(hits))
    for f in sorted(hits):                      # diagnostics on stderr only —
        print(f"  held: {f}", file=sys.stderr)   # stdout stays ONE number
    return 0 if not hits else 1


if __name__ == "__main__":
    sys.exit(main())
