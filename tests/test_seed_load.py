"""T1.5 — override + dedupe (tie-break pinned §5.7) + book_key assignment (§5.3).
Case-split per MC 12523: the whole-corpus assertions run on BOTH corpora, each
pinned to its own counts — the `personal` case (the export + its real CSVs,
wherever path F resolves them) and the `synthetic` case on the committed
synthetic corpus with tmp synthetic CSVs, which runs in every checkout. The
override/dedupe legs that used to name the diary's own titles (Evelyn/Falska
toner) now run synthetic-only, on the same-shaped synthetic rows (Eskils
fel-år-rad, Sanna tongångar dubbelvariant); the personal case still pins the
whole-table outcome so a drift on the real file lands loud here."""
import sqlite3
from pathlib import Path

import pytest

from app import db, seed

ROOT = Path(__file__).resolve().parent.parent

# Per-case aliases/overrides: personal = the repo's real CSVs; synthetic =
# rows the test itself writes (a clean clone has neither real CSV nor needs it).
PERSONAL_ALIASES = ROOT / "data-import/author_aliases.csv"
PERSONAL_OVERRIDES = ROOT / "data-import/import_overrides.csv"
SYNTH_ALIASES = ("Sissela Åhrnstedt,Sissela Åhrstedt\n"
                 "Sara H. Ohlsson,Sara H Ohlsson\n"
                 "Elsa Lindqvist,Elsie Lindqvist\n")
SYNTH_OVERRIDES = "Eskils tio äkta vänner,2025-10-26\n"

PINS = {
    "personal": {"parsed": 725, "stored": 724, "read": 706, "wishlist": 18,
                 "ratings": 6, "ljudbok": 52, "duplicates": 1},
    "synthetic": {"parsed": 43, "stored": 42, "read": 39, "wishlist": 3,
                  "ratings": 3, "ljudbok": 6, "duplicates": 1},
}


@pytest.fixture()
def seeded(corpus_case, corpus_file, tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    aliases, overrides = PERSONAL_ALIASES, PERSONAL_OVERRIDES
    if corpus_case == "synthetic":
        aliases = tmp_path / "synth_aliases.csv"
        aliases.write_text(SYNTH_ALIASES, encoding="utf-8")
        overrides = tmp_path / "synth_overrides.csv"
        overrides.write_text(SYNTH_OVERRIDES, encoding="utf-8")
    conn = db.connect()
    db.init_db(conn)
    report = seed.load(conn, corpus_file, aliases, overrides)
    yield conn, report
    conn.close()


def test_counts_match_audited_outcome(corpus_case, seeded):
    conn, report = seeded
    pin = PINS[corpus_case]
    assert report["parsed"] == pin["parsed"]
    assert report["stored"] == pin["stored"]
    assert report["duplicates"] == pin["duplicates"]
    assert conn.execute("SELECT COUNT(*) FROM book").fetchone()[0] == pin["stored"]
    assert conn.execute(
        "SELECT COUNT(*) FROM book WHERE status='read'").fetchone()[0] == pin["read"]
    assert conn.execute(
        "SELECT COUNT(*) FROM book WHERE status='wishlist'").fetchone()[0] == pin["wishlist"]
    assert conn.execute(
        "SELECT COUNT(*) FROM book WHERE rating IS NOT NULL").fetchone()[0] == pin["ratings"]
    assert conn.execute(
        "SELECT COUNT(*) FROM book WHERE format='ljudbok'").fetchone()[0] == pin["ljudbok"]
    assert report["flagged"] == []


@pytest.fixture()
def seeded_synth(synth_seed, tmp_path, monkeypatch):
    """The synthetic corpus behind the title-naming legs (MC 12523): those
    legs name their rows, and a diary title may never be named — so the
    tie-break/override mechanism runs on the synthetic rows in every clone,
    while the case-parametrized legs above keep pinning the whole-table
    outcome on both corpora."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    aliases = tmp_path / "synth_aliases.csv"
    aliases.write_text(SYNTH_ALIASES, encoding="utf-8")
    overrides = tmp_path / "synth_overrides.csv"
    overrides.write_text(SYNTH_OVERRIDES, encoding="utf-8")
    conn = db.connect()
    db.init_db(conn)
    report = seed.load(conn, synth_seed, aliases, overrides)
    yield conn, report
    conn.close()


def test_wrong_year_row_is_corrected_by_the_override_file(seeded_synth):
    conn, _ = seeded_synth
    row = conn.execute(
        "SELECT date_read FROM book WHERE title = 'Eskils tio äkta vänner'"
    ).fetchone()
    assert row == ("2025-10-26",)


def test_dedupe_tiebreak_and_reread_note(seeded_synth):
    """The pinned §5.7 tie-break, asserted on the shaped synthetic
    double-variant row."""
    conn, report = seeded_synth
    rows = conn.execute(
        "SELECT read_year, date_read, notes FROM book "
        "WHERE title = 'Sanna tongångar och sura krusbär'").fetchall()
    assert len(rows) == 1
    read_year, date_read, notes = rows[0]
    assert read_year == 2023  # MAX of 2020 vs 2023 (P3-1 tie-break)
    assert date_read is None  # both NULL -> NULL
    assert notes and "omläsning" in notes
    assert len(report["duplicates_pairs"]) == 1


def test_every_book_has_unique_book_key(corpus_case, seeded):
    conn, _ = seeded
    n = PINS[corpus_case]["stored"]
    got = conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT book_key), "
        "SUM(book_key = '' OR book_key IS NULL) FROM book").fetchone()
    assert got == (n, n, 0)


def test_reimport_is_idempotent(corpus_case, seeded, corpus_file, tmp_path):
    conn, _ = seeded
    aliases, overrides = PERSONAL_ALIASES, PERSONAL_OVERRIDES
    if corpus_case == "synthetic":
        aliases = tmp_path / "re-aliases.csv"
        aliases.write_text(SYNTH_ALIASES, encoding="utf-8")
        overrides = tmp_path / "re-overrides.csv"
        overrides.write_text(SYNTH_OVERRIDES, encoding="utf-8")
    report2 = seed.load(conn, corpus_file, aliases, overrides)
    assert report2["stored"] == PINS[corpus_case]["stored"]
    assert conn.execute("SELECT COUNT(*) FROM book").fetchone()[0] == \
        PINS[corpus_case]["stored"]


def test_book_key_is_stable_and_order_insensitive():
    k1 = seed.book_key("Boken om havet", ["Felicia Valder"])
    k2 = seed.book_key("Boken om havet", ["Felicia Valder"])
    assert k1 == k2 and len(k1) == 64
    a = seed.book_key("Kartboken", ["Lena Lindorsson Roth", "Hasse Wallinquist"])
    b = seed.book_key("Kartboken", ["Hasse Wallinquist", "Lena Lindorsson Roth"])
    assert a == b
    assert a != seed.book_key("Kartboken", ["Lena Lindorsson Roth"])
    # Pinned from the first implementation run (quoted in the T1.5 commit msg).
    assert k1 == "9db8b2d68fb95d08053694157039050486a8d47f4d477e6105f180090e4cdc59"  # MC 12523: re-pinned after the synthetic-ize (was the real-corpus key)
