"""The seed-corpus cases (path F, MC 12451 c5; two-case cut, MC 12523).

The raw seed export is personal data: it is gitignored and has NEVER been
committed (T1.8/P0-1), so a clean checkout of this repo cannot hold it. That
SUPERSEDES PLAN-c3 §13 ("missing file → the corpus tests FAIL loudly, a
pytest.skip is FORBIDDEN"): §13 could only ever run the suite where the
personal file already sat, which no verifier outside this build clone can do.

MC 12523 cuts the posture in two. Corpus-dependent legs are parametrized over
a CASE, never skipped: `synthetic` always runs — on the committed
`tests/fixtures/synthetic_seed.md`, Swedish-shaped invented rows carrying the
same parse shapes as the export — and `personal` is ADDED as a second case
wherever the export resolves (the pin doctrine keeps running its sha256 /
whole-corpus-count / digest assertions on the real file on this host). A leg
that today skips on a clean clone runs its synthetic case there instead; a
leg pinned to personal bytes it may not name (the diary's own titles, the
real CSVs) keeps a synthetic-only leg for the same mechanism and says so in
its docstring. Absence never turns an assertion green: every assertion names
the case it pins.
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

# The committed synthetic corpus (MC 12523): identical section/row shapes,
# zero personal bytes, safe to run anywhere.
SYNTH = ROOT / "tests/fixtures/synthetic_seed.md"

# The two personal CSVs, env names (MC 12532): the resolvers in app/seed.py
# are env-first, defaulting to the off-repo DATA_HOME — the REAL CSVs on the
# build host. Unpinned, those ride into legs labelled `synthetic`.
CSV_ENV_VARS = ("LISELOTT_ALIASES_FILE", "LISELOTT_OVERRIDE_FILE")


@pytest.fixture(scope="session", autouse=True)
def _suite_csv_pins(tmp_path_factory):
    """Suite-wide SYNTHETIC pin (MC 12532, sealed-flake finding 2): point
    both CSV env vars at NON-EXISTENT paths inside pytest's tmp space, so a
    leg labelled synthetic can never read the personal CSVs. The pin
    doctrine survives untouched: a leg that builds its own CSV sets its env
    per-test (monkeypatch), and the personal-CSV pin leg lifts this pin to
    fall back to the real DATA_HOME default — it still runs the real CSVs
    where they resolve."""
    base = tmp_path_factory.mktemp("csv-pins")
    prev = {var: os.environ.get(var) for var in CSV_ENV_VARS}
    for var in CSV_ENV_VARS:
        os.environ[var] = str(base / f"{var}.absent")
    yield
    for var, val in prev.items():
        if val is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = val


@pytest.fixture(scope="session", autouse=True)
def _suite_refresh_state_pin(tmp_path_factory):
    """MC 12647: pin the accepted-wave RECORD dir (AI_REK_STATE_DIR, default
    the fleet dir /home/claudecode/.liselott-rek) into pytest's tmp space
    for the whole session — a suite run can never write the fleet state.
    Legs that own the state dir move it per-test (monkeypatch), exactly
    like the per-leg AI_REK_REHEARSAL_DIR in tests/test_ai_rek_pass.kör."""
    prev = os.environ.get("AI_REK_STATE_DIR")
    os.environ["AI_REK_STATE_DIR"] = str(tmp_path_factory.mktemp("rek-state"))
    yield
    if prev is None:
        os.environ.pop("AI_REK_STATE_DIR", None)
    else:
        os.environ["AI_REK_STATE_DIR"] = prev


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
                f"{ENV_VAR}={env} names no file — the corpus gate runs the "
                "synthetic case when the export is unresolvable, never when "
                "it is misconfigured")
        return path.resolve()
    return IN_REPO.resolve() if IN_REPO.is_file() else None


def corpus_cases():
    """`synthetic` always; `personal` only where the export resolves."""
    return ["synthetic"] + (["personal"] if resolve_seed_file() else [])


def pytest_generate_tests(metafunc):
    if "corpus_case" in metafunc.fixturenames:
        metafunc.parametrize("corpus_case", corpus_cases(), ids=corpus_cases())


@pytest.fixture()
def corpus_file(corpus_case):
    """The raw seed for the parametrized case: synthetic (committed) or
    personal (the export resolved through path F; never named in a leg)."""
    if corpus_case == "personal":
        return resolve_seed_file()
    return SYNTH


@pytest.fixture()
def synth_seed():
    """The committed synthetic corpus, for legs that need no case split."""
    return SYNTH


@pytest.fixture()
def corpus():
    """The PERSONAL export only — for the pins that are meaningless on
    synthetic bytes (the diary-in-git title guard greps the real corpus; a
    committed synthetic fixture's titles living in tracked files is by
    design). Skips with a loud reason where the export is unresolvable."""
    path = resolve_seed_file()
    if path is None:
        pytest.skip("personal corpus absent — path F keeps it out of git; "
                    "run on a host holding the export or set LISELOTT_SEED_FILE")
    return path
