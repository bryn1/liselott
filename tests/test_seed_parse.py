"""T1.2 — section/entry parser + the sha256 pin (P0-1: file read from worktree,
never from git; §13: missing file FAILS this test, skipping is forbidden)."""
import hashlib
import shutil

import pytest

from app.seed import parse_file

SEED_PATH = "data-import/seed-books-raw.md"
# Pinned in PLAN-c3 (computed by the planner, not by this file's subject).
SEED_SHA256 = "420259164605b1b9e221e4e9fc8b6f5f98676f0c4bc9e4f6c02e6e5555ec24dc"

# Cycle-1 §2 census: parser counts are canonical, in-header labels are not
# (2025 lyssnade label says 12 -> 13; 2019 label says 83 -> 82).
EXPECTED_SECTIONS = {
    ("lyssnad", 2026): 20, ("läst", 2026): 2,
    ("läst", 2025): 24, ("lyssnad", 2025): 13,
    ("läst", 2024): 21, ("lyssnad", 2024): 19,
    ("läst", 2023): 69, ("läst", 2022): 76, ("läst", 2021): 83,
    ("läst", 2020): 90, ("läst", 2019): 82, ("läst", 2018): 70,
    ("läst", 2017): 55, ("läst", 2016): 53, ("läst", 2015): 30,
    ("wishlist", 0): 18,
}


@pytest.fixture()
def seed_path(tmp_path):
    from pathlib import Path
    src = Path(SEED_PATH)
    assert src.is_file(), (
        f"{src.resolve()} missing — corpus tests run on the VM350 build clone "
        "(PLAN-c3 §13); this FAILS by design, it must never skip")
    return src


def test_sha256_equals_pinned_literal(seed_path):
    got = hashlib.sha256(seed_path.read_bytes()).hexdigest()
    assert got == SEED_SHA256


def test_parse_file_returns_725_entries(seed_path):
    assert len(parse_file(seed_path)) == 725


def test_per_section_counts(seed_path):
    counts = {}
    for e in parse_file(seed_path):
        counts[(e["kind"], e["year"])] = counts.get((e["kind"], e["year"]), 0) + 1
    assert counts == EXPECTED_SECTIONS


def test_section_fields_per_kind(seed_path):
    for e in parse_file(seed_path):
        if e["kind"] == "lyssnad":
            assert (e["format"], e["status"], e["year"]) == ("ljudbok", "read", e["year"])
        elif e["kind"] == "läst":
            assert (e["format"], e["status"], e["year"]) == ("bok", "read", e["year"])
        else:
            assert (e["kind"], e["format"], e["status"], e["year"]) == (
                "wishlist", "bok", "wishlist", 0)


def test_header_region_is_parsed_nowhere(seed_path, tmp_path):
    """P2-8 proof: a fake header bullet never becomes an entry (§5.1: the
    file's lines 1-7 carry stale claims and are parsed nowhere)."""
    lines = seed_path.read_text(encoding="utf-8").splitlines(keepends=True)
    first_section = next(i for i, ln in enumerate(lines) if ln.startswith("## "))
    lines.insert(first_section, "- 991231 Fake Title av Nobody\n")
    copy = tmp_path / "seed-with-fake-header.md"
    shutil.copyfile(seed_path, copy)
    copy.write_text("".join(lines), encoding="utf-8")
    entries = parse_file(copy)
    assert len(entries) == 725  # fake bullet adds nothing
    assert not [e for e in entries if "Fake Title" in e["raw"]]
