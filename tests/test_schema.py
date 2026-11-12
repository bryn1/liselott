"""T1.1 — schema: 10 tables and the §5 constraints (P1-3 book_key, P2-3 dismissed)."""
import sqlite3

import pytest

from app import db

TABLES = {"book", "author", "book_author", "author_alias", "genre",
          "book_genre", "candidate", "dismissed", "login_attempts", "settings"}


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    c = db.connect()
    db.init_db(c)
    yield c
    c.close()


def insert_book(c, key="k-1", **over):
    row = dict(title="Testtitel", book_key=key, format="bok", read_year=2024,
               status="read", created="2026-01-01T00:00:00Z",
               updated="2026-01-01T00:00:00Z")
    row.update(over)
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    return c.execute(f"INSERT INTO book ({cols}) VALUES ({marks})", tuple(row.values()))


def test_all_ten_tables_exist(conn):
    got = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert TABLES <= got


def test_init_db_is_idempotent(conn):
    db.init_db(conn)
    assert conn.execute("SELECT COUNT(*) FROM book").fetchone()[0] == 0


def test_rating_above_five_rejected(conn):
    insert_book(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE book SET rating=6")


def test_format_cd_rejected(conn):
    with pytest.raises(sqlite3.IntegrityError):
        insert_book(conn, format="cd")


def test_dismissed_both_key_kinds_and_unique(conn):
    conn.execute("INSERT INTO dismissed (key, ts) VALUES ('book:1', 'x')")
    conn.execute("INSERT INTO dismissed (key, ts) VALUES ('cand:1', 'x')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO dismissed (key, ts) VALUES ('book:1', 'y')")


def test_tried_providers_and_enrich_fail_accepted(conn):
    insert_book(conn, tried_providers="libris,ol,gb", enrich_fail=0)
    row = conn.execute("SELECT tried_providers, enrich_fail FROM book").fetchone()
    assert row == ("libris,ol,gb", 0)


def test_book_key_not_null_unique(conn):
    insert_book(conn, key="dup")
    with pytest.raises(sqlite3.IntegrityError):
        insert_book(conn, key="dup", title="Annan")
    with pytest.raises(sqlite3.IntegrityError):
        insert_book(conn, key=None)


def test_status_check_read_wishlist_only(conn):
    insert_book(conn, key="a", status="read")
    insert_book(conn, key="b", status="wishlist")
    with pytest.raises(sqlite3.IntegrityError):
        insert_book(conn, key="c", status="done")
