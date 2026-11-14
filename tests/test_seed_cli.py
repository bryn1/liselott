"""T1.6 — importer CLI (§5.9): thin caller over app/seed.py, exit 0 only on
the audited counts, loud failure naming a validator-flagged row.
Corpus leg (path F, MC 12451 c5): every leg runs the CLI on the export the
`corpus` fixture resolves — skipped with a loud reason where none is
resolvable, pinned to the audited counts where one is."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "data-import/import_seed.py"

AUDITED = {"parsed": 725, "stored": 724, "duplicates": 1,
           "ratings": 6, "ljudbok": 52}


def run_cli(db_path, raw_path):
    return subprocess.run(
        [sys.executable, str(CLI), "--db", str(db_path), "--raw", str(raw_path)],
        cwd=ROOT, capture_output=True, text=True)


def test_cli_exit0_and_audited_counts(corpus, tmp_path):
    db = tmp_path / "seed.db"
    proc = run_cli(db, corpus)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == AUDITED
    assert (tmp_path / "import_report.json").is_file()


def test_cli_rerun_is_idempotent(corpus, tmp_path):
    db = tmp_path / "seed.db"
    assert run_cli(db, corpus).returncode == 0
    second = run_cli(db, corpus)
    assert second.returncode == 0, second.stderr
    assert json.loads(second.stdout) == AUDITED  # stored stays 724


def test_cli_names_which_count_is_which(corpus, tmp_path):
    """F-L4b (MC 12451 c4): `stored` in this line is §5.9's AUDITED outcome —
    the whole table — while POST /seed's `stored=` is the rows that POST
    stored. One word, two readings, and a re-run is exactly where they differ:
    the CLI then says so (and says nothing when the fresh import makes them
    the same number). stdout's pinned payload is untouched — the sentence is
    stderr copy, and the delta also lands in import_report.json."""
    db = tmp_path / "seed.db"
    first = run_cli(db, corpus)
    assert "hyllans totala antal" not in first.stderr   # fresh: 724 = 724
    second = run_cli(db, corpus)
    assert "hyllans totala antal rader" in second.stderr
    assert "tillförde 0" in second.stderr
    report = json.loads((tmp_path / "import_report.json").read_text())
    assert report["stored"] == 724 and report["stored_now"] == 0


def test_cli_refuses_validator_flagged_row_and_names_it(corpus, tmp_path):
    bad = tmp_path / "seed-bad.md"
    text = corpus.read_text(encoding="utf-8")
    # tab-form av-separator: the literal ' av ' split can't see it, the §5.4
    # validator flags it -> CLI must exit nonzero naming the row.
    bad.write_text(text + "\n- Nån trasig titel av Författare\tav\tNågon\n",
                   encoding="utf-8")
    proc = run_cli(tmp_path / "seed.db", bad)
    assert proc.returncode != 0
    assert "Nån trasig titel" in proc.stderr
