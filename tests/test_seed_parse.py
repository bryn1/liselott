"""T1.2 — section/entry parser + the sha256 pins (P0-1: files read from the
worktree, never from git). Case-split per MC 12523: the `personal` case pins
the real export (sha + parse counts, pinned in PLAN-c3 by the planner) and
runs wherever path F resolves it; the `synthetic` case pins the committed
tests/fixtures/synthetic_seed.md (sha computed by MC 12523 when it landed) and
runs in every checkout — a clean clone runs this whole file, it skips nothing.
"""
import hashlib

from app.seed import parse_file

# Per-case pins: the same assertions, each pinned to its own corpus.
PINS = {
    "personal": {
        "sha256": "420259164605b1b9e221e4e9fc8b6f5f98676f0c4bc9e4f6c02e6e5555ec24dc",
        "entries": 725,
        # Cycle-1 §2 census: parser counts are canonical, in-header labels are
        # not (2025 lyssnade label says 12 -> 13; 2019 label says 83 -> 82).
        "sections": {
            ("lyssnad", 2026): 20, ("läst", 2026): 2,
            ("läst", 2025): 24, ("lyssnad", 2025): 13,
            ("läst", 2024): 21, ("lyssnad", 2024): 19,
            ("läst", 2023): 69, ("läst", 2022): 76, ("läst", 2021): 83,
            ("läst", 2020): 90, ("läst", 2019): 82, ("läst", 2018): 70,
            ("läst", 2017): 55, ("läst", 2016): 53, ("läst", 2015): 30,
            ("wishlist", 0): 18,
        },
    },
    "synthetic": {
        "sha256": "925e70a56b51979501e5070869a4fe197875be8ec09161cdc6c24efaf380e25b",
        "entries": 43,
        "sections": {
            ("läst", 2026): 10, ("lyssnad", 2026): 4,
            ("läst", 2025): 13, ("lyssnad", 2025): 2,
            ("läst", 2024): 5, ("läst", 2023): 4, ("läst", 2020): 2,
            ("wishlist", 0): 3,
        },
    },
}


def test_sha256_equals_pinned_literal(corpus_case, corpus_file):
    got = hashlib.sha256(corpus_file.read_bytes()).hexdigest()
    assert got == PINS[corpus_case]["sha256"]


def test_parse_file_entry_count(corpus_case, corpus_file):
    assert len(parse_file(corpus_file)) == PINS[corpus_case]["entries"]


def test_per_section_counts(corpus_case, corpus_file):
    counts = {}
    for e in parse_file(corpus_file):
        counts[(e["kind"], e["year"])] = counts.get((e["kind"], e["year"]), 0) + 1
    assert counts == PINS[corpus_case]["sections"]


def test_section_fields_per_kind(corpus_file):
    for e in parse_file(corpus_file):
        if e["kind"] == "lyssnad":
            assert (e["format"], e["status"], e["year"]) == ("ljudbok", "read", e["year"])
        elif e["kind"] == "läst":
            assert (e["format"], e["status"], e["year"]) == ("bok", "read", e["year"])
        else:
            assert (e["kind"], e["format"], e["status"], e["year"]) == (
                "wishlist", "bok", "wishlist", 0)


def test_header_region_is_parsed_nowhere(corpus_case, corpus_file, tmp_path):
    """P2-8 proof: a fake header bullet never becomes an entry (§5.1: the
    file's header prose carries stale claims and is parsed nowhere)."""
    lines = corpus_file.read_text(encoding="utf-8").splitlines(keepends=True)
    first_section = next(i for i, ln in enumerate(lines) if ln.startswith("## "))
    lines.insert(first_section, "- 991231 Fake Title av Nobody\n")
    copy = tmp_path / "seed-with-fake-header.md"
    copy.write_text("".join(lines), encoding="utf-8")
    entries = parse_file(copy)
    assert len(entries) == PINS[corpus_case]["entries"]  # fake bullet adds nothing
    assert not [e for e in entries if "Fake Title" in e["raw"]]
