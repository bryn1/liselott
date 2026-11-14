"""T1.7 — whole-corpus drift gate WITHOUT committing the diary (P0-1).
Digest + aggregates only (scripts/parse_digest.py); literals pinned per case
(MC 12523): the `personal` pins are the planner-audited digest of the real
export (runs wherever path F resolves it); the `synthetic` pins are the same
gate over the committed synthetic corpus — computed by scripts/parse_digest.py
when it landed, so a clean clone runs the drift-gate mechanism too."""
import json
import subprocess
import sys
from pathlib import Path

from app import seed

ROOT = Path(__file__).resolve().parent.parent

# Pinned literals per case — digest over (section,row,title,authors,date,
# rating) of every row, produced by scripts/parse_digest.py on each file.
PINS = {
    "personal": {
        "sha256": "79ec15d92af259c80bca615208e120617cd7f2c7c854cc15714974551ef21d76",
        "aggregates": {
            "entries": 725, "with_date": 45, "with_rating": 6, "ljudbok": 52,
            "sections": {
                "lyssnad:2026": 20, "läst:2026": 2, "läst:2025": 24,
                "lyssnad:2025": 13, "läst:2024": 21, "lyssnad:2024": 19,
                "läst:2023": 69, "läst:2022": 76, "läst:2021": 83,
                "läst:2020": 90, "läst:2019": 82, "läst:2018": 70,
                "läst:2017": 55, "läst:2016": 53, "läst:2015": 30,
                "wishlist:0": 18,
            },
        },
        # the personal corpus carries exactly one " af " author; the name is
        # the diary's own and is never named here (MC 12523).
        "af_names": None,
    },
    "synthetic": {
        "sha256": "2630a7c5f589f1c8e7847b0ade5564225e371dccc70209bc85a633b2d7d74da7",
        "aggregates": {
            "entries": 43, "with_date": 36, "with_rating": 3, "ljudbok": 6,
            "sections": {
                "läst:2026": 10, "lyssnad:2026": 4, "läst:2025": 13,
                "lyssnad:2025": 2, "läst:2024": 5, "läst:2023": 4,
                "läst:2020": 2, "wishlist:0": 3,
            },
        },
        "af_names": ["Ragna Bonde af Gennarp"],
    },
}


def test_digest_and_aggregates_equal_pinned_literals(corpus_case, corpus_file):
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/parse_digest.py"),
                           str(corpus_file)],
                          cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    got = json.loads(proc.stdout)
    assert got["sha256"] == PINS[corpus_case]["sha256"]  # any row change flips it
    for key, expected in PINS[corpus_case]["aggregates"].items():
        assert got[key] == expected, key


def _rows(corpus):
    out = []
    for e in seed.parse_file(corpus):
        out.append((e, seed.parse_row(e["raw"])))
    return out


def test_invariants_over_every_parsed_row(corpus_case, corpus_file):
    bad_av_author, bad_title_annotation, af_rows, av_ending = [], [], [], []
    for entry, row in _rows(corpus_file):
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
    assert len(af_rows) == 1  # the census: exactly one " af " name in a corpus
    if PINS[corpus_case]["af_names"] is not None:
        assert af_rows == PINS[corpus_case]["af_names"]
    assert av_ending == []
