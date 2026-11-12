"""T1.6 — importer CLI (§5.9): thin caller over app/seed.py, exit 0 only on
the audited counts, loud failure naming a validator-flagged row.
VM350 corpus leg (§13)."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "data-import/import_seed.py"
RAW = ROOT / "data-import/seed-books-raw.md"

AUDITED = {"parsed": 725, "stored": 724, "duplicates": 1,
           "ratings": 6, "ljudbok": 52}


def run_cli(db_path, raw_path):
    return subprocess.run(
        [sys.executable, str(CLI), "--db", str(db_path), "--raw", str(raw_path)],
        cwd=ROOT, capture_output=True, text=True)


def test_cli_exit0_and_audited_counts(tmp_path):
    assert RAW.is_file(), f"{RAW} missing — VM350 build clone leg (§13), never skip"
    db = tmp_path / "seed.db"
    proc = run_cli(db, RAW)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == AUDITED
    assert (tmp_path / "import_report.json").is_file()


def test_cli_rerun_is_idempotent(tmp_path):
    db = tmp_path / "seed.db"
    assert run_cli(db, RAW).returncode == 0
    second = run_cli(db, RAW)
    assert second.returncode == 0, second.stderr
    assert json.loads(second.stdout) == AUDITED  # stored stays 724


def test_cli_refuses_validator_flagged_row_and_names_it(tmp_path):
    bad = tmp_path / "seed-bad.md"
    text = RAW.read_text(encoding="utf-8")
    # tab-form av-separator: the literal ' av ' split can't see it, the §5.4
    # validator flags it -> CLI must exit nonzero naming the row.
    bad.write_text(text + "\n- Nån trasig titel av Författare\tav\tNågon\n",
                   encoding="utf-8")
    proc = run_cli(tmp_path / "seed.db", bad)
    assert proc.returncode != 0
    assert "Nån trasig titel" in proc.stderr
