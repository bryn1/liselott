"""T6.3 — the candidate builder, the CLI's --authors wiring, and the P1-4
floor reference (PLAN-c3 §14 + cycle-1 §8 pipeline: OL author search top 10,
skip titles owned by a book, cap 40 authors per pass, 90-day refresh,
idempotent — rerun never duplicates).

ONE mechanism: the CLI runs enrich_loop.candidates_pass — the very function
POST /backfill?mode=candidates drives (test_backfill_route owns the route
legs; nothing here re-tests the cursor). The fixture transport answers the
author search; no socket in the suite (§13)."""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app import db, enrich_ol, seed
from app import enrich_loop
from scripts.enrich_backfill import main

NO_PACE = lambda seconds: None                                    # noqa: E731


def seed_library(conn, n_authors=1):
    """One READ book per author — the queue §8 names (the authors of the
    diary), so author_queue has work for the builder."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for i in range(1, n_authors + 1):
        conn.execute("INSERT INTO book (id, title, format, read_year, status,"
                     " book_key, created, updated) VALUES (?,?,?,?,?,?,?,?)",
                     (200 + i, f"Läst bok {i}", "bok", 2025, "read",
                      f"lib-{i}", now, now))
        conn.execute("INSERT INTO author (id, name) VALUES (?,?)",
                     (i, f"Kvikka Författare {i}"))
        conn.execute("INSERT INTO book_author (book_id, author_id)"
                     " VALUES (?,?)", (200 + i, i))
    conn.commit()


@pytest.fixture()
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    conn = db.connect()
    db.init_db(conn)
    seed_library(conn)
    yield conn, tmp_path
    conn.close()


def hits(n, name):
    return [{"title": f"Spetsade titlar {k} av {name}", "isbn13": None,
             "year": 2024, "authors": [name]} for k in range(n)]


def stale_iso(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")


def candidates_of(conn):
    return conn.execute("SELECT author_name, title FROM candidate"
                        " ORDER BY author_name, title").fetchall()


# ── the builder legs (plan's five) ───────────────────────────────────────────
def test_author_search_top_ten_lands_ten_candidates(library):
    conn, _ = library
    now, stale = enrich_loop.candidates_window()
    queue = enrich_loop.author_queue(conn)
    report = enrich_loop.candidates_pass(
        conn, queue, lambda name: hits(10, name),
        now=now, stale_before=stale, aliases={})
    assert report["fetched"] == 1 and report["new_candidates"] == 10
    assert len(candidates_of(conn)) == 10


def test_build_author_url_requests_the_top_ten():
    """Cycle-1 §8 pins TOP 10 for the author search — the book-search
    LIMIT (5) must not silently decide the candidates' breadth too."""
    url = enrich_ol.build_author_url("Ann-Helén Laestadius")
    assert "limit=10" in url


def test_author_name_is_alias_resolved_at_insert(library):
    """An OL hit credited 'Simona Ahrnsredt' lands as the canonical
    'Simona Ahrnstedt' (the §8 seam: T1.4's alias chain AT INSERT)."""
    conn, _ = library
    now, stale = enrich_loop.candidates_window()
    queue = enrich_loop.author_queue(conn)
    enrich_loop.candidates_pass(
        conn, queue,
        lambda name: [{"title": "Villa vid havet", "authors":
                       ["Simona Ahrnsredt"], "isbn13": None, "year": 2020}],
        now=now, stale_before=stale, aliases=seed.app_aliases())
    stored = candidates_of(conn)
    assert ("Simona Ahrnstedt", "Villa vid havet") in stored


def test_rerun_adds_zero_candidates(library):
    conn, _ = library
    now, stale = enrich_loop.candidates_window()
    queue = enrich_loop.author_queue(conn)
    first = enrich_loop.candidates_pass(
        conn, queue, lambda name: hits(3, name),
        now=now, stale_before=stale, aliases={})
    second = enrich_loop.candidates_pass(
        conn, enrich_loop.author_queue(conn), lambda name: hits(3, name),
        now=now, stale_before=stale, aliases={})
    assert first["new_candidates"] == 3
    assert second["fetched"] == 0 and second["new_candidates"] == 0
    assert len(candidates_of(conn)) == 3


def test_existing_book_titles_never_enter_the_pool(library):
    """'Läst bok 1' is OWNED — an OL hit under that title (different case,
    a diacritic twist) never lands; the pool is what she does not have."""
    conn, _ = library
    now, stale = enrich_loop.candidates_window()
    queue = enrich_loop.author_queue(conn)
    enrich_loop.candidates_pass(
        conn, queue,
        lambda name: [{"title": "LÄST BOK 1", "authors": [name],
                       "isbn13": None, "year": None},
                      {"title": "Helt ny titel", "authors": [name],
                       "isbn13": None, "year": None}],
        now=now, stale_before=stale, aliases={})
    titles = [t for _, t in candidates_of(conn)]
    assert titles == ["Helt ny titel"]


def test_ninety_day_refresh_asks_stale_authors_again(library):
    conn, _ = library
    now, stale = enrich_loop.candidates_window()
    enrich_loop.candidates_pass(
        conn, enrich_loop.author_queue(conn), lambda name: hits(2, name),
        now=now, stale_before=stale, aliases={})
    conn.execute("UPDATE candidate SET fetched_at = ?", (stale_iso(120),))
    conn.commit()
    again = enrich_loop.candidates_pass(
        conn, enrich_loop.author_queue(conn), lambda name: hits(2, name),
        now=now, stale_before=stale, aliases={})
    assert again["fetched"] == 1                    # stale → re-asked
    assert again["new_candidates"] == 0             # dedupe: nothing lands twice


# ── the T6.3 completion of the builder (s5's named residual) ─────────────────
def test_pen_named_freshness_travels_the_alias_chain(tmp_path, monkeypatch):
    """The residual s5 handed over: freshness keyed only on the canonical
    name re-asks an author whose candidates sit under a spelling the DB
    KNOWS as hers. With an author_alias row 'Eva Swedenmark' → the author, a
    fresh candidate credited 'Eva Swedenmark' IS fresh for 'Ewa Swedenmark'.
    """
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    conn = db.connect()
    db.init_db(conn)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute("INSERT INTO book (id, title, format, read_year, status,"
                 " book_key, created, updated) VALUES (1, 'Min bok', 'bok',"
                 " 2025, 'read', 'k1', ?, ?)", (now, now))
    conn.execute("INSERT INTO author (id, name) VALUES (1,"
                 " 'Ewa Swedenmark')")
    conn.execute("INSERT INTO book_author (book_id, author_id) VALUES (1, 1)")
    conn.execute("INSERT INTO author_alias (alias, author_id)"
                 " VALUES ('Eva Swedenmark', 1)")
    conn.execute("INSERT INTO candidate (title, author_name, fetched_at)"
                 " VALUES ('Pennamsverk', 'Eva Swedenmark', ?)", (now,))
    conn.commit()
    now_iso, stale = enrich_loop.candidates_window()
    asked = []
    report = enrich_loop.candidates_pass(
        conn, enrich_loop.author_queue(conn),
        lambda name: asked.append(name) or [],
        now=now_iso, stale_before=stale, aliases={})
    assert report["fetched"] == 0 and asked == []    # NOT re-asked
    conn.close()


def test_provider_failure_is_counted_not_fatal(tmp_path, monkeypatch):
    """A 429/timeout posture (ProviderUnavailable — the T3 transport
    vocabulary) must not kill a 247-author live pass: the author is counted
    as a failure, the pass continues, and because nothing fresh landed for
    her the NEXT plain re-run asks her again. Same posture as the covers
    loop: a failing row is examined and passed, never poison."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    conn = db.connect()
    db.init_db(conn)
    seed_library(conn, n_authors=3)
    from app import enrich_loop
    from app.enrich_http import ProviderUnavailable

    def flaky(name):
        if name.endswith(" 2"):
            raise ProviderUnavailable("fixture: 429")
        return hits(1, name)

    now, stale = enrich_loop.candidates_window()
    r1 = enrich_loop.candidates_pass(
        conn, enrich_loop.author_queue(conn), flaky,
        now=now, stale_before=stale, aliases={})
    assert r1["fetched"] == 3 and r1["failures"] == 1
    assert r1["new_candidates"] == 2                 # the other two landed
    asked2 = []
    r2 = enrich_loop.candidates_pass(                # re-run: only the
        conn, enrich_loop.author_queue(conn),        # failed author is owed
        lambda name: asked2.append(name) or [],
        now=now, stale_before=stale, aliases={})
    assert r2["fetched"] == 1 and asked2 == ["Kvikka Författare 2"]
    conn.close()


def test_cap_forty_authors_asked_per_pass(tmp_path, monkeypatch):
    """§8's cap is 40 authors per pass: 45 queued authors, one candidate
    each — pass 1 asks exactly 40, pass 2 finds them fresh and finishes the
    remaining 5. The cap bounds the network, never the scan."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    conn = db.connect()
    db.init_db(conn)
    seed_library(conn, n_authors=45)
    now, stale = enrich_loop.candidates_window()
    p1 = enrich_loop.candidates_pass(
        conn, enrich_loop.author_queue(conn), lambda name: hits(1, name),
        now=now, stale_before=stale, aliases={},
        max_fetch=enrich_loop.MAX_AUTHORS_PER_PASS)
    assert p1["scanned"] == 45 and p1["fetched"] == 40
    p2 = enrich_loop.candidates_pass(
        conn, enrich_loop.author_queue(conn), lambda name: hits(1, name),
        now=now, stale_before=stale, aliases={},
        max_fetch=enrich_loop.MAX_AUTHORS_PER_PASS)
    assert p2["fetched"] == 5 and p2["new_candidates"] == 5
    assert conn.execute("SELECT COUNT(*) FROM candidate").fetchone()[0] == 45
    conn.close()


# ── the CLI wiring (scripts/enrich_backfill.py --authors) ────────────────────
def test_cli_authors_runs_the_shared_builder_and_reports(library, capsys):
    conn, tmp = library
    rc = main(["--authors", "--report", str(tmp / "cand.json")],
              author_search=lambda name: hits(10, name), pace=NO_PACE)
    assert rc == 0
    report = json.loads((tmp / "cand.json").read_text(encoding="utf-8"))
    assert report["mode"] == "candidates"
    assert report["total"] == 1                      # one queued author
    assert report["new_candidates"] == 10
    assert report["candidate_total"] == 10
    assert report["candidate_total"] == len(candidates_of(conn))
    line = capsys.readouterr().out
    assert "new_candidates=10" in line and "mode=candidates" in line


def test_cli_authors_limit_bounds_the_batch(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    conn = db.connect()
    db.init_db(conn)
    seed_library(conn, n_authors=5)
    rc = main(["--authors", "--limit", "2",
               "--report", str(tmp_path / "r.json")],
              author_search=lambda name: hits(1, name), pace=NO_PACE)
    assert rc == 0
    report = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert report["processed"] == 2 and report["total"] == 5
    conn.close()


def test_cli_authors_dry_run_mutates_nothing(library, capsys):
    conn, tmp = library
    rc = main(["--authors", "--dry-run", "--report", str(tmp / "d.json")],
              author_search=lambda name: pytest.fail("dry-run must not ask"),
              pace=NO_PACE)
    assert rc == 0
    assert conn.execute("SELECT COUNT(*) FROM candidate").fetchone()[0] == 0
    report = json.loads((tmp / "d.json").read_text(encoding="utf-8"))
    assert report["dry_run"] is True
    assert report["planned"] == [1]                  # the author it WOULD ask
    assert "dry_run=True" in capsys.readouterr().out


def test_cli_offline_authors_refuses_loudly(library, capsys):
    """--offline means no network; the candidate pool IS a network fetch.
    Refusing loudly is the honest answer (the P2-b defect class is a flag
    that quietly does nothing, not a flag that says no)."""
    conn, tmp = library
    rc = main(["--authors", "--offline", "--report", str(tmp / "x.json")],
              author_search=lambda name: pytest.fail("offline must not ask"),
              pace=NO_PACE)
    assert rc == 2
    assert "kandidat" in capsys.readouterr().err.lower()
    assert conn.execute("SELECT COUNT(*) FROM candidate").fetchone()[0] == 0


def test_cli_report_default_path_is_the_one_named_file(tmp_path, monkeypatch):
    """P2-f: --report wins; without it the report lands EXACTLY at
    state_base()/enrich_report.json — the one path, also for this mode."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    conn = db.connect()
    db.init_db(conn)
    seed_library(conn)
    rc = main(["--authors"], author_search=lambda name: hits(1, name),
              pace=NO_PACE)
    assert rc == 0
    report = json.loads((tmp_path / "enrich_report.json").read_text(
        encoding="utf-8"))
    assert report["mode"] == "candidates" and report["candidate_total"] == 1
    conn.close()
