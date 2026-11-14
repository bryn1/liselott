"""T1.5 — override + dedupe (tie-break pinned §5.7) + book_key assignment (§5.3).
Corpus leg (path F, MC 12451 c5): reads the gitignored raw export through the
`corpus` fixture — skipped with a loud reason where no export is resolvable,
fully asserted where one is."""
import sqlite3
from pathlib import Path

import pytest

from app import db, seed

ROOT = Path(__file__).resolve().parent.parent
ALIASES = ROOT / "data-import/author_aliases.csv"
OVERRIDES = ROOT / "data-import/import_overrides.csv"


@pytest.fixture()
def seeded(corpus, tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    conn = db.connect()
    db.init_db(conn)
    report = seed.load(conn, corpus, ALIASES, OVERRIDES)
    yield conn, report
    conn.close()


def test_counts_match_audited_outcome(seeded):
    conn, report = seeded
    assert report["parsed"] == 725
    assert report["stored"] == 724
    assert report["duplicates"] == 1
    assert conn.execute("SELECT COUNT(*) FROM book").fetchone()[0] == 724
    assert conn.execute(
        "SELECT COUNT(*) FROM book WHERE status='read'").fetchone()[0] == 706
    assert conn.execute(
        "SELECT COUNT(*) FROM book WHERE status='wishlist'").fetchone()[0] == 18
    assert conn.execute(
        "SELECT COUNT(*) FROM book WHERE rating IS NOT NULL").fetchone()[0] == 6
    assert conn.execute(
        "SELECT COUNT(*) FROM book WHERE format='ljudbok'").fetchone()[0] == 52
    assert report["flagged"] == []


def test_evelyn_date_override(seeded):
    conn, _ = seeded
    row = conn.execute(
        "SELECT date_read FROM book WHERE title = 'Evelyn Hugos sju äkta män'"
    ).fetchone()
    assert row == ("2025-10-26",)


def test_falska_toner_dedupe_tiebreak(seeded):
    conn, report = seeded
    rows = conn.execute(
        "SELECT read_year, date_read, notes FROM book "
        "WHERE title = 'Falska toner och söta vinbär'").fetchall()
    assert len(rows) == 1
    read_year, date_read, notes = rows[0]
    assert read_year == 2023  # MAX of 2020 vs 2023 (P3-1 tie-break)
    assert date_read is None  # both NULL -> NULL
    assert notes and "omläsning" in notes
    assert len(report["duplicates_pairs"]) == 1


def test_every_book_has_unique_book_key(seeded):
    conn, _ = seeded
    n, distinct, empty = conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT book_key), "
        "SUM(book_key = '' OR book_key IS NULL) FROM book").fetchone()
    assert (n, distinct, empty) == (724, 724, 0)


def test_reimport_is_idempotent(seeded, corpus):
    conn, report1 = seeded
    report2 = seed.load(conn, corpus, ALIASES, OVERRIDES)
    assert report2["stored"] == 724
    assert conn.execute("SELECT COUNT(*) FROM book").fetchone()[0] == 724


def test_book_key_is_stable_and_order_insensitive():
    k1 = seed.book_key("Ett hav av minnen", ["Fiona Valpy"])
    k2 = seed.book_key("Ett hav av minnen", ["Fiona Valpy"])
    assert k1 == k2 and len(k1) == 64
    a = seed.book_key("Atlas", ["Lucinda Riley", "Harry Whittaker"])
    b = seed.book_key("Atlas", ["Harry Whittaker", "Lucinda Riley"])
    assert a == b
    assert a != seed.book_key("Atlas", ["Lucinda Riley"])
    # Pinned from the first implementation run (quoted in the T1.5 commit msg).
    assert k1 == "6d38cc142282ccf0bf06a921de95ae392a1a6361d137181d48b41fd858f5ebf2"
