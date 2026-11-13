"""F-A (TEST-verdict 2026-11-13) — the shelf groups the CORPUS SHAPE.

The shipped group_for_shelf was RUN-LENGTH over sort_by_read_date output;
with ~90 % NULL date_read (the real corpus: 661 of 706 read rows) that block
runs in title order and every year change opened a NEW section — 583 <h2>
over 12 real years on the seeded shelf, newest-first violated at 260/582
pairs, and the gate's plants M5/M9 (one section per book — the exact
measured shape) left the full 422-test suite GREEN. The blind spot dies
here: ~300 read rows across 2015–2026 INTERLEAVED, 90 % NULL date_read, 3
read rows on the 0-year sentinel, + 2 wishes. Asserted through THE REAL
bibliotek.html on the app test client: ONE <section class="grupp"> and ONE
<h2> per group (12 years + "Utan år" + "Att läsa" = 14), headings strictly
descending with no repeats, wishes LAST — and every group internally in the
sort_by_read_date order the template must not shuffle.
"""
import re
import sqlite3
from datetime import datetime, timezone

import pytest

from app import create_app
from app.books import group_for_shelf, load_books
from app.db import init_db
from app.text import fold

PASSWORD = "_test_losenord_"
N_READ = 300                       # ~300 read rows, corpus-scale shape
N_NOYEAR = 3                       # read rows on the 0 sentinel → "Utan år"
N_WISH = 2
YEARS = list(range(2026, 2014, -1))                    # 2026 down to 2015
EXPECTED_HEADINGS = [str(y) for y in YEARS] + ["Utan år", "Att läsa"]


def corpus_rows():
    """(title, read_year, date_read, status) — the real shape, not 5 tidy
    rows: every 10th read row dated (→ 90 % NULL), years interleaved so the
    title-ordered NULL block jumps years on EVERY row (gcd(5,12)=1: each of
    the 12 years appears 25×)."""
    rows = []
    for i in range(N_READ):
        year = 2015 + (i * 5) % 12
        date = f"{year}-06-15" if i % 10 == 0 else None
        rows.append((f"Titel {i:03d}", year, date, "read"))
    rows += [(f"Utanårs {i}", 0, None, "read") for i in range(N_NOYEAR)]
    rows += [(f"Önska {w}", 0, None, "wishlist") for w in range(N_WISH)]
    return rows


@pytest.fixture()
def shelf(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    conn = sqlite3.connect(tmp_path / "liselott.db")
    init_db(conn)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for bid, (title, year, date_read, status) in enumerate(corpus_rows(),
                                                           start=1):
        conn.execute(
            "INSERT INTO book (id, title, year, read_year, date_read,"
            " format, status, book_key, created, updated)"
            " VALUES (?,?,?,?,?,'bok',?,?,?,?)",
            (bid, title, None, year, date_read, status,
             f"key-{bid}", now, now))
    conn.commit()
    conn.close()
    app = create_app()
    app.testing = True
    client = app.test_client()
    assert client.post("/liselott/satt-loesenord",
                       data={"loesenord": PASSWORD,
                             "bekrafta": PASSWORD}).status_code == 302
    return client, tmp_path


def headings(html):
    return re.findall(r"<h2[^>]*>([^<]+)</h2>", html)


def loaded(tmp_path):
    conn = sqlite3.connect(tmp_path / "liselott.db")
    try:
        return load_books(conn)
    finally:
        conn.close()


def assert_internal_order(rows):
    """sort_by_read_date's contract INSIDE a group: dated rows first, dates
    non-increasing; the NULL tail in folded-title order (the two stable
    sorts, asserted on the data — not by re-calling the sort itself)."""
    dated = [b for b in rows if b["date_read"]]
    undated = [b for b in rows if not b["date_read"]]
    assert rows[:len(dated)] == dated
    dates = [b["date_read"] for b in dated]
    assert dates == sorted(dates, reverse=True)
    titles = [fold(b["title"]) for b in undated]
    assert titles == sorted(titles)


# ── rendered page: THE real template, counted markers ───────────────────────
def test_one_section_per_year_headings_strictly_descending(shelf):
    client, _ = shelf
    html = client.get("/liselott/bibliotek").get_data(as_text=True)
    seen = headings(html)
    assert seen == EXPECTED_HEADINGS       # dedup + order + no repeats, and
    assert len(set(seen)) == len(seen)     # wishes last / "Utan år" second-last
    years = [int(h) for h in seen[:-2]]
    assert all(a > b for a, b in zip(years, years[1:]))


def test_section_and_h2_markers_count_groups_not_books(shelf):
    client, _ = shelf
    html = client.get("/liselott/bibliotek").get_data(as_text=True)
    assert html.count('<section class="grupp"') == len(EXPECTED_HEADINGS)
    assert html.count("<h2") == len(EXPECTED_HEADINGS)
    # every card is still ON the page — dedup groups, it never drops rows
    assert html.count('class="bok-kort"') == N_READ + N_NOYEAR + N_WISH


def test_wishlist_section_is_last(shelf):
    client, _ = shelf
    html = client.get("/liselott/bibliotek").get_data(as_text=True)
    pos = html.index(">Att läsa<")
    assert pos > html.index(">Utan år<")
    for w in range(N_WISH):
        assert html.index(f"Önska {w}") > pos


# ── the unit: keyed grouping, order preserved ───────────────────────────────
def test_groups_keyed_on_year_values_not_runs(shelf):
    _, tmp_path = shelf
    grupper = group_for_shelf(loaded(tmp_path))
    assert [g[0] for g in grupper] == YEARS + ["Utan år", "Att läsa"]
    for label, rows in grupper:
        assert rows                                   # no empty group
        assert_internal_order(rows)
        if isinstance(label, int):                    # every row is its year
            assert all(b["read_year"] == label for b in rows)


def test_undated_read_rows_form_one_trailing_group(shelf):
    _, tmp_path = shelf
    grupper = dict(group_for_shelf(loaded(tmp_path)))
    utan = grupper["Utan år"]
    assert len(utan) == N_NOYEAR
    assert "Att läsa" in list(grupper)[-1]            # wishlist stays last
