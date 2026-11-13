"""The cover_source CHECK migration (s3 §9 open finding, closed by S5's UI).

A CHECK constraint is baked into SQLite at CREATE TABLE: widening the
cover_source vocabulary to 'manual-url' (the OQ-2 ruling, commit 7eee210)
changed app/schema.sql but cannot touch a table that already exists. s3
flagged it honestly — "any pre-existing DB needs recreation before S5's UI can
use the helper" — and S5 is that UI, so this stage ships the NAMED, TESTED
migration instead of a recreation runbook. Copy-of-existing-state semantics:
the fixture below is a DB built with the PRE-7eee210 DDL and rows already in
it; the migration runs against THAT, never against a fresh DB.

The legs: the widened value is accepted after migrate (before: IntegrityError
— the RED this test was written against); every row, id and link survives the
rebuild; the book indexes come back (DROP TABLE takes them with it); re-run is
a no-op (idempotent); a DB already on the new schema is not rewritten; and an
unknown column shape ABORTS LOUDLY rather than silently dropping data.
"""
import sqlite3

import pytest

from app import db
from app.db import init_db

# The two affected tables EXACTLY as they were before 7eee210 (git show
# 7eee210^:app/schema.sql) — the historical state under migration. The rest of
# the schema arrives through the real init_db (IF NOT EXISTS leaves these old
# tables alone — which is precisely the bug: executescript never widens them).
OLD_BOOK_DDL = """
CREATE TABLE book (
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, isbn13 TEXT, isbn10 TEXT,
  year INTEGER, format TEXT NOT NULL CHECK (format IN ('bok','ljudbok')),
  date_read TEXT,
  read_year INTEGER NOT NULL,
  rating INTEGER CHECK (rating BETWEEN 1 AND 5),
  notes TEXT,
  cover_path TEXT, cover_source TEXT CHECK (cover_source IN ('libris','googlebooks','openlibrary','manual')),
  status TEXT NOT NULL DEFAULT 'read' CHECK (status IN ('read','wishlist')),
  book_key TEXT NOT NULL UNIQUE,
  tried_providers TEXT,
  enrich_fail INTEGER NOT NULL DEFAULT 0,
  created TEXT NOT NULL, updated TEXT NOT NULL);
"""
OLD_CANDIDATE_DDL = """
CREATE TABLE candidate (id INTEGER PRIMARY KEY, title TEXT NOT NULL, author_name TEXT, isbn13 TEXT,
  year INTEGER, cover_path TEXT, cover_source TEXT CHECK (cover_source IN ('libris','googlebooks','openlibrary','manual')),
  fetched_at TEXT NOT NULL);
"""


def old_seeded_db(path):
    """A pre-existing, SEEDED DB in the old shape (copy-of-existing-state).
    The rest of the schema arrives through the RAW schema.sql script — NOT
    through init_db, because init_db now also MIGRATES, and this fixture must
    stop at the exact pre-migration state the legs start from."""
    conn = sqlite3.connect(path)
    conn.executescript(OLD_BOOK_DDL + OLD_CANDIDATE_DDL)
    conn.execute("INSERT INTO book (id, title, format, read_year, book_key,"
                 " cover_source, created, updated) VALUES"
                 " (1, 'Stöld', 'bok', 2025, 'key-stold', 'openlibrary',"
                 " '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')")
    conn.execute("INSERT INTO book (id, title, format, read_year, book_key,"
                 " created, updated) VALUES"
                 " (2, 'God jul Agnes', 'bok', 2026, 'key-agnes',"
                 " '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')")
    conn.execute("INSERT INTO candidate (id, title, author_name, fetched_at)"
                 " VALUES (1, 'Kandidat', 'Författare', '2026-01-01T00:00:00Z')")
    conn.commit()
    conn.executescript(db.SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def stored_ddl(conn, table):
    return conn.execute("SELECT sql FROM sqlite_master WHERE type='table'"
                        " AND name = ?", (table,)).fetchone()[0]


def test_widened_value_is_rejected_before_and_accepted_after(tmp_path):
    conn = old_seeded_db(tmp_path / "liselott.db")
    with pytest.raises(sqlite3.IntegrityError):    # the s3 §9 fact, asserted
        conn.execute("UPDATE book SET cover_source = 'manual-url' WHERE id = 2")
    conn.rollback()
    init_db(conn)                                   # <- runs the migration
    conn.execute("UPDATE book SET cover_source = 'manual-url' WHERE id = 2")
    conn.commit()   # no IntegrityError: the UI this stage ships can now write
    conn.close()


def test_every_row_and_link_survives_the_rebuild(tmp_path):
    conn = old_seeded_db(tmp_path / "liselott.db")
    conn.execute("INSERT INTO author (id, name) VALUES (7, 'Ann-Helén Laestadius')")
    conn.execute("INSERT INTO book_author (book_id, author_id) VALUES (1, 7)")
    conn.commit()
    before = conn.execute("SELECT id, title, book_key, cover_source FROM book"
                          " ORDER BY id").fetchall()
    init_db(conn)
    assert conn.execute("SELECT id, title, book_key, cover_source FROM book"
                        " ORDER BY id").fetchall() == before
    # ids survive (cover files live at covers/<id>.jpg — an id renumber would
    # orphan every stored cover); links and the candidate row are intact too
    assert conn.execute("SELECT book_id, author_id FROM book_author").fetchall() \
        == [(1, 7)]
    assert conn.execute("SELECT title FROM candidate").fetchone()[0] == "Kandidat"
    conn.close()


def test_the_book_indexes_come_back(tmp_path):
    conn = old_seeded_db(tmp_path / "liselott.db")
    init_db(conn)
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master"
                                        " WHERE type='index'")}
    for idx in ("idx_book_title", "idx_book_date", "idx_book_year"):
        assert idx in names            # DROP TABLE took them; migrate restores
    conn.close()


def test_the_unique_book_key_contract_still_holds(tmp_path):
    """The UNIQUE on book_key is the P1-3 upsert match key — a rebuild that
    quietly loses it would let the bundle POST duplicate books in production."""
    conn = old_seeded_db(tmp_path / "liselott.db")
    init_db(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO book (title, format, read_year, book_key,"
                     " created, updated) VALUES ('x', 'bok', 2026,"
                     " 'key-stold', 't', 't')")
    conn.close()


def test_migrate_is_idempotent(tmp_path):
    conn = old_seeded_db(tmp_path / "liselott.db")
    init_db(conn)
    after_first = (stored_ddl(conn, "book"), stored_ddl(conn, "candidate"))
    init_db(conn)                      # second pass must not rewrite anything
    assert (stored_ddl(conn, "book"), stored_ddl(conn, "candidate")) == after_first
    conn.close()


def test_a_db_on_the_new_schema_is_not_touched(tmp_path):
    """The fresh-build case: init_db on an empty dir creates the widened DDL
    straight from schema.sql and migrate must leave it byte-identical."""
    conn = sqlite3.connect(tmp_path / "liselott.db")
    init_db(conn)
    fresh = stored_ddl(conn, "book")
    init_db(conn)
    assert stored_ddl(conn, "book") == fresh
    conn.close()


def test_an_unknown_column_shape_aborts_loudly(tmp_path):
    """Data-loss guard: a future DB carrying a column today's DDL does not
    know must abort naming it — silently copying only the intersection is how
    a migration eats a user's data."""
    conn = old_seeded_db(tmp_path / "liselott.db")
    conn.execute("ALTER TABLE book ADD COLUMN framtida_falt TEXT")
    conn.commit()
    with pytest.raises(RuntimeError, match="framtida_falt"):
        init_db(conn)
    # the abort left the real table intact, not half-rebuilt
    assert conn.execute("SELECT COUNT(*) FROM book").fetchone()[0] == 2
    cols = [r[1] for r in conn.execute("PRAGMA table_info(book)")]
    assert "framtida_falt" in cols                 # nothing was rewritten away
    conn.close()
