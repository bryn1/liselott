"""T1.7 — whole-corpus drift gate WITHOUT committing the diary (P0-1).
Digest + aggregates only (scripts/parse_digest.py); literals pinned from the
planner-audited corpus run on this VM350 build clone. VM350 corpus leg (§13)."""
import json
import subprocess
import sys
from pathlib import Path

from app import seed

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data-import/seed-books-raw.md"

# Pinned literals — digest over (section,row,title,authors,date,rating) of
# all 725 rows, produced by scripts/parse_digest.py on the sha-pinned file.
PINNED_SHA256 = "79ec15d92af259c80bca615208e120617cd7f2c7c854cc15714974551ef21d76"
PINNED_AGGREGATES = {
    "entries": 725, "with_date": 45, "with_rating": 6, "ljudbok": 52,
    "sections": {
        "lyssnad:2026": 20, "läst:2026": 2, "läst:2025": 24, "lyssnad:2025": 13,
        "läst:2024": 21, "lyssnad:2024": 19, "läst:2023": 69, "läst:2022": 76,
        "läst:2021": 83, "läst:2020": 90, "läst:2019": 82, "läst:2018": 70,
        "läst:2017": 55, "läst:2016": 53, "läst:2015": 30, "wishlist:0": 18,
    },
}


def test_digest_and_aggregates_equal_pinned_literals():
    assert RAW.is_file(), f"{RAW} missing — VM350 build clone leg (§13), never skip"
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/parse_digest.py")],
                          cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    got = json.loads(proc.stdout)
    assert got["sha256"] == PINNED_SHA256  # any field change in any row flips it
    for key, expected in PINNED_AGGREGATES.items():
        assert got[key] == expected, key


def _rows():
    out = []
    for e in seed.parse_file(RAW):
        out.append((e, seed.parse_row(e["raw"])))
    return out


def test_invariants_over_every_parsed_row():
    bad_av_author, bad_title_annotation, af_rows, av_ending = [], [], [], []
    for entry, row in _rows():
        for a in row["authors"]:
            if " av " in a:
                bad_av_author.append((entry["raw"], a))
            if " af " in a:
                af_rows.append(a)
        if "i källan" in row["title"] or "(utan datum)" in row["title"]:
            bad_title_annotation.append(entry["raw"])
        if row["title"].endswith(" av"):
            av_ending.append(entry["raw"])
    assert bad_av_author == [], f"{len(bad_av_author)} authors carry ' av '"
    assert bad_title_annotation == []
    assert len(af_rows) == 1 and af_rows[0] == "Louise Boije af Gennäs"
    assert av_ending == []
