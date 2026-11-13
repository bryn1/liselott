"""T3.5 — the backfill CLI, tested OFFLINE (plan §13: live calls belong to this
script, never to the suite). Flags are EXACTLY the plan's set: --dry-run
--limit N --offline --authors --report PATH (P2-b: NO --only-missing flag
exists — the default scope already targets rows missing isbn/cover).

The test drives main() with an injected fixture transport (the same seam the
providers use), so the pipeline is exercised end to end without a socket:
counts line up, --dry-run writes NOTHING, --report <path> writes EXACTLY
there (P2-f), and the default report path is state_base()/enrich_report.json."""
import json
import sqlite3
from pathlib import Path

import pytest

from app import db, enrich_ol
from scripts.enrich_backfill import main

ROOT = Path(__file__).resolve().parent.parent
OL_FIXTURE = ROOT / "tests" / "fixtures" / "ol_stold.json"
COVER_FIXTURE = ROOT / "tests" / "fixtures" / "cover_sample.jpg"

TITLES = ["Stöld", "Den andra boken", "Tredje boken"]


@pytest.fixture()
def build_db(tmp_path, monkeypatch):
    """A tiny stand-in for the VM350 build DB: three books, none enriched."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    conn = db.connect()
    db.init_db(conn)
    for i, title in enumerate(TITLES):
        conn.execute(
            "INSERT INTO book (title, book_key, format, read_year, status, created, updated)"
            " VALUES (?, ?, 'bok', 2024, 'read', '2026-01-01T00:00:00Z', "
            "'2026-01-01T00:00:00Z')", (title, f"key-{i}"))
    conn.commit()
    yield conn, tmp_path
    conn.close()


def fixture_transports(conn=None, **kw):
    """libris answers nothing, gb is not consulted (cooldown), and ol answers:
    for "Stöld" with the RECORDED fixture (the real mapping path), for the
    other titles with an exactly-matching synthetic hit — the match policy
    (T3.4) is live here too, and a wrong-title answer must NOT resolve a row."""
    docs = json.loads(OL_FIXTURE.read_text(encoding="utf-8"))

    def libris(title, authors):
        return []

    def ol(title, authors):
        if title == "Stöld":
            return enrich_ol.map_docs(docs)
        return [{"source": "openlibrary", "title": title, "authors": list(authors),
                 "isbn13": "9789198559699", "isbn10": "9198559699", "year": 2024,
                 "cover_id": 77, "cover_url": "https://covers.openlibrary.org/b/id/77-M.jpg",
                 "subjects": ["Crime, Detective stories"]}]

    return {"libris": libris, "ol": ol, "gb": None}


NO_PACE = lambda seconds: None


def cover_fetch(url, **kw):
    return COVER_FIXTURE.read_bytes()


def test_offline_limit_50_exits_zero_and_the_report_is_consistent(build_db, capsys):
    conn, tmp = build_db
    rc = main(["--offline", "--limit", "50", "--report", str(tmp / "rep.json")],
              transports=fixture_transports(), fetch=cover_fetch,
              pace=NO_PACE)
    assert rc == 0
    report = json.loads((tmp / "rep.json").read_text(encoding="utf-8"))
    assert report["scanned"] == 3                  # every missing row was looked at
    assert report["processed"] == 3
    assert report["isbn_resolved"] == 3            # the fixture answers for all
    assert report["covers_stored"] == 3
    assert report["failures"] == 0
    assert report["total"] == 3                    # total missing rows in scope
    assert report["offline"] is True and report["writes"] == 0
    rows = conn.execute("SELECT isbn13, cover_path FROM book").fetchall()
    assert all(r[0] is None and r[1] is None for r in rows), \
        "--offline rehearses: it never dirties the evidence columns"
    assert "isbn_resolved=3" in capsys.readouterr().out


def test_dry_run_mutates_nothing(build_db):
    conn, tmp = build_db
    before = conn.execute("SELECT * FROM book ORDER BY id").fetchall()
    rc = main(["--dry-run", "--report", str(tmp / "rep.json")],
              transports=fixture_transports(), fetch=cover_fetch,
              pace=NO_PACE)
    assert rc == 0
    assert conn.execute("SELECT * FROM book ORDER BY id").fetchall() == before
    report = json.loads((tmp / "rep.json").read_text(encoding="utf-8"))
    assert report["dry_run"] is True and report["processed"] == 0
    assert report["planned"] == [1, 2, 3]          # what a live run WOULD take


def test_report_path_is_written_exactly_there(build_db, tmp_path_factory):
    conn, tmp = build_db
    elsewhere = tmp_path_factory.mktemp("report-dir") / "custom-name.json"
    rc = main(["--offline", "--report", str(elsewhere)],
              transports=fixture_transports(), fetch=cover_fetch,
              pace=NO_PACE)
    assert rc == 0
    assert elsewhere.exists()                      # EXACTLY there (P2-f)
    assert not (tmp / "enrich_report.json").exists()


def test_default_report_lands_in_state_base(build_db):
    conn, tmp = build_db
    rc = main(["--offline"], transports=fixture_transports(), fetch=cover_fetch,
              pace=NO_PACE)
    assert rc == 0
    assert (tmp / "enrich_report.json").exists()   # default = state_base()/…


def test_limit_bounds_the_work(build_db):
    conn, tmp = build_db
    rc = main(["--offline", "--limit", "2", "--report", str(tmp / "r.json")],
              transports=fixture_transports(), fetch=cover_fetch,
              pace=NO_PACE)
    report = json.loads((tmp / "r.json").read_text(encoding="utf-8"))
    assert rc == 0 and report["processed"] == 2 and report["total"] == 3


def test_live_mode_writes_and_resumes_on_what_is_left(build_db):
    """The DEFAULT scope is rows missing isbn/cover (P2-b: that IS the flag —
    no --only-missing exists), so a second run after a partial pass continues."""
    conn, tmp = build_db
    assert main(["--report", str(tmp / "r.json"), "--limit", "1"],
                transports=fixture_transports(), fetch=cover_fetch,
              pace=NO_PACE) == 0
    remaining = conn.execute(
        "SELECT COUNT(*) FROM book WHERE isbn13 IS NULL OR cover_path IS NULL").fetchone()[0]
    assert remaining == 2
    assert main(["--report", str(tmp / "r2.json")],
                transports=fixture_transports(), fetch=cover_fetch,
              pace=NO_PACE) == 0
    report = json.loads((tmp / "r2.json").read_text(encoding="utf-8"))
    assert report["scanned"] == 2 and report["total"] == 2
    assert conn.execute("SELECT COUNT(*) FROM book WHERE isbn13 IS NULL").fetchone()[0] == 0


def test_authors_flag_refuses_loudly_rather_than_lying(build_db, capsys):
    """--authors is the plan's flag for the candidate pool, whose build is
    T6.3; a flag that quietly did nothing would be the P2-b defect itself."""
    conn, tmp = build_db
    assert main(["--authors"], transports=fixture_transports()) == 2
    captured = capsys.readouterr()
    assert "kandidatpool" in captured.err and "T6.3" in captured.err


def test_pacing_is_one_request_per_second(build_db):
    """1 req/s is a plan rule (§12): every CONSULTED provider call goes through
    the pace hook first; here the hook is a counter, not a sleep."""
    conn, tmp = build_db
    ticks = []
    assert main(["--offline", "--report", str(tmp / "r.json")],
                transports=fixture_transports(), fetch=cover_fetch,
                pace=ticks.append) == 0
    # one tick per OUTBOUND request: libris + ol + the cover download per row
    # (gb is skipped, so it costs nothing) — 3 rows × 3 requests:
    assert ticks == [1.0] * 9


def no_isbn_transports():
    """A provider that MATCHES the row but carries no isbn — the case that
    tells `matched` and `isbn_resolved` apart."""
    def libris(title, authors):
        return []

    def ol(title, authors):
        return [{"source": "openlibrary", "title": title, "authors": list(authors),
                 "isbn13": None, "isbn10": None, "year": 2024, "cover_id": None,
                 "cover_url": None, "subjects": []}]
    return {"libris": libris, "ol": ol, "gb": None}


def test_isbn_resolved_counts_written_isbns_not_matches(build_db):
    """The loop's second pass caught this: `isbn_resolved` is the DoD's floor
    metric, so it must count isbn13 values actually WRITTEN. Counting matched
    rows instead made a re-run report 54 "resolved" while writing nothing new —
    a number that flatters the pipeline, which is exactly what a floor metric
    must never do. `matched` is the separate, honest count."""
    conn, tmp = build_db
    assert main(["--report", str(tmp / "p1.json")], transports=fixture_transports(),
                fetch=cover_fetch, pace=NO_PACE) == 0
    first = json.loads((tmp / "p1.json").read_text(encoding="utf-8"))
    assert first["isbn_resolved"] == 3 and first["matched"] == 3
    # every row has an isbn AND a cover now: the scope is empty and a plain
    # re-run reports 0 of everything — that IS the F-2 convergence signal
    assert main(["--report", str(tmp / "p2.json")], transports=fixture_transports(),
                fetch=cover_fetch, pace=NO_PACE) == 0
    second = json.loads((tmp / "p2.json").read_text(encoding="utf-8"))
    assert second["total"] == 0 and second["matched"] == 0 and second["isbn_resolved"] == 0
    # a match whose provider had no isbn: matched yes, isbn_resolved never
    conn.execute("UPDATE book SET isbn13 = NULL, cover_path = NULL, "
                 "cover_source = NULL WHERE id = 1")
    conn.commit()
    assert main(["--report", str(tmp / "p3.json")], transports=no_isbn_transports(),
                fetch=cover_fetch, pace=NO_PACE) == 0
    third = json.loads((tmp / "p3.json").read_text(encoding="utf-8"))
    assert third["matched"] == 1 and third["isbn_resolved"] == 0
    assert conn.execute("SELECT isbn13 FROM book WHERE id = 1").fetchone()[0] is None


def test_the_report_attributes_every_gain_to_the_provider_that_gave_it(build_db):
    """The floors are judged per lane (owner ruling 2026-11-13): a miss must say
    WHICH provider missed, or the number teaches nothing. The fixture set gives
    isbn+genres via OpenLibrary and covers via OpenLibrary too, so attribution
    must be able to separate a lane that resolved from a lane that stored."""
    conn, tmp = build_db
    main(["--report", str(tmp / "r.json")], transports=fixture_transports(),
         fetch=cover_fetch, pace=NO_PACE)
    report = json.loads((tmp / "r.json").read_text(encoding="utf-8"))
    by = report["by_source"]
    assert by["openlibrary"]["matched"] == 3 and by["openlibrary"]["isbn"] == 3
    assert by["openlibrary"]["covers"] == 3
    assert by["libris"]["matched"] == 0 and by["libris"]["isbn"] == 0
