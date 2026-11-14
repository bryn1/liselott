"""T1.6 — importer CLI (§5.9): thin caller over app/seed.py, exit 0 only on
the audited counts, loud failure naming a validator-flagged row.
Case-split per MC 12523: the `personal` case pins §5.9's audited outcome on
the real export (wherever path F resolves it); the `synthetic` case runs the
same CLI on the committed synthetic corpus — where the counts CANNOT equal
the personal audited table, so the case pins the other direction of the same
gate: a count drift makes the CLI exit nonzero and name the diff. Both
cases run; a clean clone loses nothing silently."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "data-import/import_seed.py"

AUDITED = {"parsed": 725, "stored": 724, "duplicates": 1,
           "ratings": 6, "ljudbok": 52}
# The synthetic corpus's own table — it deliberately differs from AUDITED.
SYNTH_COUNTS = {"parsed": 43, "stored": 42, "duplicates": 1,
                "ratings": 3, "ljudbok": 6}
EXPECTED_RC = {"personal": 0, "synthetic": 1}
TABLE = {"personal": AUDITED, "synthetic": SYNTH_COUNTS}


def run_cli(db_path, raw_path):
    return subprocess.run(
        [sys.executable, str(CLI), "--db", str(db_path), "--raw", str(raw_path)],
        cwd=ROOT, capture_output=True, text=True)


def test_cli_exit_code_and_counts(corpus_case, corpus_file, tmp_path):
    db = tmp_path / "seed.db"
    proc = run_cli(db, corpus_file)
    assert proc.returncode == EXPECTED_RC[corpus_case], proc.stderr
    assert json.loads(proc.stdout) == TABLE[corpus_case]
    assert (tmp_path / "import_report.json").is_file()
    if corpus_case == "synthetic":
        # the drift gate's other direction, live: counts differ from §5.9's
        # audited table -> the refusal names both tables and lands on stderr.
        assert "differ from audited" in proc.stderr


def test_cli_rerun_is_idempotent(corpus_case, corpus_file, tmp_path):
    db = tmp_path / "seed.db"
    assert run_cli(db, corpus_file).returncode == EXPECTED_RC[corpus_case]
    second = run_cli(db, corpus_file)
    assert second.returncode == EXPECTED_RC[corpus_case], second.stderr
    assert json.loads(second.stdout) == TABLE[corpus_case]  # stored stays put


def test_cli_names_which_count_is_which(corpus_case, corpus_file, tmp_path):
    """F-L4b (MC 12451 c4): `stored` in this line is §5.9's AUDITED outcome —
    the whole table — while POST /seed's `stored=` is the rows that POST
    stored. One word, two readings, and a re-run is exactly where they differ:
    the CLI then says so (and says nothing when the fresh import makes them
    the same number). stdout's pinned payload is untouched — the sentence is
    stderr copy, and the delta also lands in import_report.json."""
    db = tmp_path / "seed.db"
    first = run_cli(db, corpus_file)
    assert "hyllans totala antal" not in first.stderr   # fresh: table = stored_now
    second = run_cli(db, corpus_file)
    assert "hyllans totala antal rader" in second.stderr
    assert "tillförde 0" in second.stderr
    report = json.loads((tmp_path / "import_report.json").read_text())
    assert report["stored"] == TABLE[corpus_case]["stored"] and \
        report["stored_now"] == 0


def test_cli_refuses_validator_flagged_row_and_names_it(corpus_file, tmp_path):
    bad = tmp_path / "seed-bad.md"
    text = corpus_file.read_text(encoding="utf-8")
    # tab-form av-separator: the literal ' av ' split can't see it, the §5.4
    # validator flags it -> CLI must exit nonzero naming the row.
    bad.write_text(text + "\n- Nån trasig titel av Författare\tav\tNågon\n",
                   encoding="utf-8")
    proc = run_cli(tmp_path / "seed.db", bad)
    assert proc.returncode != 0
    assert "Nån trasig titel" in proc.stderr
