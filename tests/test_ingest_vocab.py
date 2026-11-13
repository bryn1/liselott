"""F-A2 (DA-verdict-c2, MC 12451) — the VALUE VOCABULARY at the ingest doors.

A /bundle line with a non-integer read_year used to be ACCEPTED with 200 and
stored as TEXT (the INTEGER column has affinity, not constraint); the shelf
then sorted mixed int/str keys and raised TypeError — the owner's home page,
500 on every GET, until someone repaired the DB by hand. Two defence lines,
both the wave's own idiom:

(a) THE WRITE door refuses with the named-line 400 the parse vocabulary
    already owns for rating/status/cover_source: read_year must be an int
    (never bool), the 0 sentinel, a 4-digit year, or absent — nothing
    stored on refusal;
(b) THE READ MODEL survives anyway — books.py:group_for_shelf, tested in
    tests/test_shelf_grouping.py: one guarded int conversion so sorted()
    never sees a non-int key;
(c) THE SEED PATH regression leg: the section regex's \\d{4} group is the
    reason no seed body can ever yield a TEXT year — pinned here so a
    loosened regex is a RED test, not a shelf brick.
"""
import sqlite3

import pytest

from tests.test_seed_routes import authed, bundle_bytes, line, stored_count


@pytest.mark.parametrize("value",
                         ["okänt-2025", "2025", 2024.0, True, False, [2024],
                          {"y": 2024}, 99, -5])
def test_bundle_refuses_a_non_integer_read_year_naming_the_line(authed, value):
    """(a) every malformed year shape 400s naming the 1-based line (the
    shipped answer was 200), and COUNT(read_year values) proves the line
    stored NOTHING — not the row, not the year."""
    tmp, client = authed
    r = client.post("/liselott/bundle", data=bundle_bytes(
        line(book_key="kA", title="Bok med skadat år", read_year=value)),
        content_type="application/octet-stream")
    assert r.status_code == 400, repr(value)
    assert "rad 1" in r.get_data(as_text=True), repr(value)
    assert stored_count(tmp) == 0
    conn = sqlite3.connect(tmp / "liselott.db")
    try:
        years = conn.execute("SELECT COUNT(*) FROM book"
                             " WHERE read_year IS NOT NULL"
                             "   AND read_year != 0").fetchone()[0]
    finally:
        conn.close()
    assert years == 0


def test_bundle_accepts_the_legal_year_shapes(authed):
    """The vocabulary refuses garbage WITHOUT touching the legal shapes the
    §5.11 contract exports: a plain int year, the wishline 0 sentinel and
    an absent (null) year all still pass parse and land."""
    tmp, client = authed
    r = client.post("/liselott/bundle", data=bundle_bytes(
        line(book_key="kInt", title="Riktigt år", read_year=2019),
        line(book_key="kGammal", title="Gammal goding", read_year=1850),
        line(book_key="kNoll", title="Önskelinjen", read_year=0,
             status="wishlist"),
        line(book_key="kTom", title="Utan år", read_year=None)),
        content_type="application/octet-stream")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["inserted"] == 4


def test_seed_path_cannot_produce_a_text_year(authed):
    """(c): the seed core reads the year ONLY from the section header's
    \\d{4} group — a header carrying a text year is an unknown section and
    400s, nothing stored. Regression leg: if that regex ever loosens, a
    TEXT year reaches read_year through the seed door too, and this dies."""
    tmp, client = authed
    r = client.post("/liselott/seed", data=(
        "## Lästa böcker okänt-2025\n- 250101 En bok av Aino A\n").encode(),
        content_type="application/octet-stream")
    assert r.status_code == 400
    assert "okänd sektion" in r.get_data(as_text=True)
    assert stored_count(tmp) == 0
