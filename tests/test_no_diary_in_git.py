"""T1.8 — diary-in-git guard (P0-1). Three legs:
leg1 structural scan (corpus-free): no tracked file carries ≥100 seed-entry
     shape lines; leg2 corpus scan (path F, MC 12451 c5 — the `corpus` fixture
     skips it with a loud reason where the personal export is unresolvable, and
     it runs wherever the export exists): no tracked file contains ≥20 whole
     seed titles (K=20 —
     the 18 T1.3 goldens stay under); leg3 never-committed: the seed md,
     golden_parse.json and seed-bundle* appear in NO ls-files entry and the
     first two are check-ignore-clean. Works in ANY clone for legs 1+3."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Seed-entry shape per the T1.8/T8.3 gate (POSIX classes written in Python syntax).
SEED_LINE_RE = re.compile(r"^\s*-\s+((\d{6})\s+)?.{3,}\sav\s.*")
MAX_SHAPE_LINES = 100      # leg1: legit test files carry ≤18
MAX_TITLES = 20            # leg2: K pinned; T1.3 goldens = 18


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.splitlines()


def tracked_files():
    return [f for f in git("ls-files") if (ROOT / f).is_file()]


def leg1_shape_scan():
    leaks = []
    for f in tracked_files():
        n = sum(1 for ln in (ROOT / f).read_text(encoding="utf-8", errors="replace")
                .splitlines() if SEED_LINE_RE.match(ln))
        if n >= MAX_SHAPE_LINES:
            leaks.append((f, n))
    return leaks


def leg2_title_scan(raw):
    sys.path.insert(0, str(ROOT))
    from app import seed
    titles = {seed.parse_row(e["raw"])["title"]
              for e in seed.parse_file(raw)}
    leaks = []
    for f in tracked_files():
        text = (ROOT / f).read_text(encoding="utf-8", errors="replace")
        hits = {t for t in titles if t and t in text}
        if len(hits) >= MAX_TITLES:
            leaks.append((f, len(hits)))
    return leaks


def test_leg1_no_tracked_file_looks_like_the_diary():
    assert leg1_shape_scan() == []


def test_leg2_no_tracked_file_holds_20_whole_seed_titles(corpus):
    assert leg2_title_scan(corpus) == []


def test_leg3_diary_artifacts_never_committed():
    tracked = tracked_files()
    for f in tracked:
        assert f != "data-import/seed-books-raw.md"
        assert not f.endswith("golden_parse.json")
        assert "seed-bundle" not in Path(f).name
    for p in ("data-import/seed-books-raw.md", "tests/fixtures/golden_parse.json"):
        rc = subprocess.run(["git", "check-ignore", "-q", p], cwd=ROOT)
        assert rc.returncode == 0, f"{p} is not gitignored"
