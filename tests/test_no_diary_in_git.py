"""T1.8 — diary-in-git guard (P0-1). Three legs:
leg1 structural scan (corpus-free): no file in the guard's universe carries
     ≥100 seed-entry shape lines; leg2 corpus scan (path F, MC 12451 c5 — the
     `corpus` fixture skips it with a loud reason where the personal export is
     unresolvable, and it runs wherever the export exists): no file in the
     universe contains ≥20 whole seed titles (K=20 — the 18 T1.3 goldens stay
     under); leg3 never-committed: the seed md, golden_parse.json and
     seed-bundle* appear in NO entry of the universe, and where .git exists
     the first two are additionally check-ignore-clean.
The universe is the COMMITTED files. With .git it is `git ls-files`,
cross-checked against a walk of the checked-out tree: the two mechanisms must
agree, and a tracked file the walk cannot see is reported loudly. Without .git
— the sealed re-run checks the commit out via `git archive | tar -x`, so there
is no git metadata — the export IS exactly the committed files, so the walk
alone is the universe. No .git never skips a leg: this is an absence guard, it
runs everywhere and FAILS loudly on a planted personal file."""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HAS_GIT = (ROOT / ".git").exists()  # dir (clone) or file (worktree); absent in an archive export
# Seed-entry shape per the T1.8/T8.3 gate (POSIX classes written in Python syntax).
SEED_LINE_RE = re.compile(r"^\s*-\s+((\d{6})\s+)?.{3,}\sav\s.*")
MAX_SHAPE_LINES = 100      # leg1: legit test files carry ≤18
MAX_TITLES = 20            # leg2: K pinned; T1.3 goldens = 18
# Never tree content: repo metadata, envs, audit scratch (in a sealed archive
# export only the pytest caches below can even appear — what a run leaves).
SCRATCH_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
                ".git", ".venv", "venv", ".audits", ".tmp"}
DIARY_ARTIFACTS = ("data-import/seed-books-raw.md",
                   "tests/fixtures/golden_parse.json")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.splitlines()


def tree_walk():
    """Every file in the checked-out tree as ROOT-relative posix paths."""
    found = set()
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SCRATCH_DIRS]
        found.update((Path(dirpath, name).relative_to(ROOT)).as_posix()
                     for name in filenames)
    return found


def universe():
    """The committed files — the guard's universe, in any checkout form.

    With .git: git ls-files cross-checked against the tree walk, so one
    mechanism reports the other's blind spot instead of silently diverging.
    Without .git: the walk itself; a `git archive` export contains exactly
    the committed files, so scanning it IS the committed-files claim."""
    walked = tree_walk()
    if HAS_GIT:
        tracked = {f for f in git("ls-files") if (ROOT / f).is_file()}
        blind = sorted(tracked - walked)
        assert not blind, (
            f"guard mechanisms disagree: ls-files tracks files the tree "
            f"walk cannot see: {blind}")
        return sorted(tracked)
    return sorted(walked)


def leg1_shape_scan():
    leaks = []
    for f in universe():
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
    for f in universe():
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
    committed = universe()
    for f in committed:
        assert f != "data-import/seed-books-raw.md"
        assert not f.endswith("golden_parse.json")
        assert "seed-bundle" not in Path(f).name
    if HAS_GIT:
        # check-ignore is a git-metadata question, meaningful only in a
        # clone; the loop above already asserts absence in BOTH forms.
        for p in DIARY_ARTIFACTS:
            rc = subprocess.run(["git", "check-ignore", "-q", p], cwd=ROOT)
            assert rc.returncode == 0, f"{p} is not gitignored"
