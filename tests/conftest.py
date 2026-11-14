"""The ONE seed-corpus locator and the corpus-leg skip gate (path F, MC 12451 c5).

The raw seed export is personal data: it is gitignored and has NEVER been
committed (T1.8/P0-1), so a clean checkout of this repo cannot hold it. That
SUPERSEDES PLAN-c3 §13 ("missing file → the corpus tests FAIL loudly, a
pytest.skip is FORBIDDEN"): §13 could only ever run the suite where the
personal file already sat, which no verifier outside this build clone can do.

The posture now: a corpus-dependent test SKIPS with the reason below when the
export is not resolvable, and RUNS its pinned assertions — sha256, parse
counts, dedupe, leak matrix — where it is. Absence never turns an assertion
green: it skips, visibly (`pytest -rs` prints the reason per skipped leg), and
the pin never weakens on a host that holds the corpus.
"""
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ENV_VAR = "LISELOTT_SEED_FILE"
# The one known in-repo location, byte-identical to `data-import/import_seed.py`
# --raw default and to `scripts/parse_digest.py`'s, so the suite and the CLIs
# resolve the corpus through the same path. It is gitignored — path F.
IN_REPO = ROOT / "data-import/seed-books-raw.md"

SKIP_REASON = ("personal corpus absent — path F keeps it out of git; "
               "run on a host holding the export or set LISELOTT_SEED_FILE")


def resolve_seed_file():
    """LISELOTT_SEED_FILE wins, else the known locations, else None.

    A set-but-unreadable LISELOTT_SEED_FILE is operator error, not absence: it
    raises (the leg ERRORs loudly) instead of skipping into a quiet green.
    """
    env = os.environ.get(ENV_VAR)
    if env:
        path = Path(env).expanduser()
        if not path.is_file():
            raise AssertionError(
                f"{ENV_VAR}={env} names no file — the corpus gate skips only "
                "when the export is unresolvable, never when it is misconfigured")
        return path.resolve()
    return IN_REPO.resolve() if IN_REPO.is_file() else None


@pytest.fixture()
def corpus():
    """The pinned raw seed file as a Path, or a loud skip where there is none."""
    path = resolve_seed_file()
    if path is None:
        pytest.skip(SKIP_REASON)
    return path
