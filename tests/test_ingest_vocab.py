"""F-A2 + F-D2/F-G2/F-E2 (DA-verdict-c2, MC 12451) — the VALUE VOCABULARY and
the honest answer at the ingest doors.

A /bundle line with a non-integer read_year used to be ACCEPTED with 200 and
stored as TEXT (the INTEGER column has affinity, not constraint); the shelf
then sorted mixed int/str keys and raised TypeError — the owner's home page,
500 on every GET, until someone repaired the DB by hand. Three defence lines,
all the wave's own idiom:

(a) THE WRITE door refuses with the named-line 400 the parse vocabulary
    already owns for rating/status/cover_source: EVERY scalar the line can
    carry is typed at the door (F-D2's three 500s and F-G2's silent garbage
    share this root — one vocabulary pass, not one patch per family), so a
    list book_key, a dict date_read, a string-in-authors or a 400-megapixel
    bomb cover all 400 naming the line instead of raising through the door;
(b) THE READ MODEL survives anyway — books.py:group_for_shelf, tested in
    tests/test_shelf_grouping.py: one guarded int conversion so sorted()
    never sees a non-int key;
(c) THE SEED PATH regression leg: the section regex's \\d{4} group is the
    reason no seed body can ever yield a TEXT year — pinned here so a
    loosened regex is a RED test, not a shelf brick.

And F-E2: a POST the WSGI layer hands over WITHOUT Content-Length (the
chunked shape) reads as an EMPTY body — caps compared against zero and the
door 200'd "inserted: 0" for bytes it never saw. Both doors now answer 411
Length Required instead of guessing.
"""
import base64
import io
import json
import sqlite3
import struct
import zlib

import pytest

from tests.test_seed_routes import (B64, authed, bundle_bytes, line,
                                    stored_count)


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


# ── F-D2/F-G2 (b): every scalar typed at the door — never a 500, never silent
@pytest.mark.parametrize("bad", [["a", "b"], {"k": 1}],
                         ids=["list", "dict"])
def test_bundle_refuses_a_non_string_book_key_naming_the_line(authed, bad):
    """F-D2 leg 1 (shipped: 500 TypeError — an unhashable list reached the
    `in seen` duplicate-check INSIDE parse, outside every handler). The
    book_key is text or the line 400s naming the 1-based line, like every
    other refusal; nothing stores."""
    tmp, client = authed
    r = client.post("/liselott/bundle", data=bundle_bytes(
        line(book_key=bad, title="Listnyckel")),
        content_type="application/octet-stream")
    assert r.status_code == 400, r.get_data(as_text=True)
    assert "rad 1" in r.get_data(as_text=True)
    assert stored_count(tmp) == 0


@pytest.mark.parametrize("field", ["date_read", "year", "isbn13", "title"])
@pytest.mark.parametrize("bad", [{"y": 2022}, ["2022"]], ids=["dict", "list"])
def test_bundle_refuses_container_values_in_scalar_fields_naming_them(
        authed, field, bad):
    """F-D2 leg 2 + F-G2 (shipped: 500 sqlite3.InterfaceError at the INSERT —
    the per-line catch only knew IntegrityError; and a plain string in
    authors/genres used to STORE silently as single characters). Every
    scalar field is text-or-number-or-none by the door's own vocabulary:
    containers die in the named-line 400, nothing stores."""
    tmp, client = authed
    r = client.post("/liselott/bundle", data=bundle_bytes(
        line(**{"book_key": "kF", "title": "Fältfel", **{field: bad}})),
        content_type="application/octet-stream")
    assert r.status_code == 400, r.get_data(as_text=True)
    assert "rad 1" in r.get_data(as_text=True)
    assert stored_count(tmp) == 0


@pytest.mark.parametrize("field", ["authors", "genres"])
def test_bundle_refuses_a_bare_string_where_a_list_belong(authed, field):
    """F-G2's named garbage: "genres":"skönlitteratur" stored ELEVEN
    single-char genres (the code iterates the string); an authors string
    corrupts the same way. A list of texts or nothing — 400 naming the
    line, nothing stores."""
    tmp, client = authed
    r = client.post("/liselott/bundle", data=bundle_bytes(
        line(book_key="kG", title="Listfusk", **{field: "skönlitteratur"})),
        content_type="application/octet-stream")
    assert r.status_code == 400, r.get_data(as_text=True)
    assert "rad 1" in r.get_data(as_text=True)
    assert stored_count(tmp) == 0


# ── F-L2 (c4): the lone surrogate — json-LEGAL text the utf-8 bind refuses ──
def sur_line(**kw) -> str:
    """A §5.11 line whose text carries a lone surrogate, dumped with the
    default ensure_ascii=True: the SURROGATE ESCAPE is what makes the line
    json-legal, so this is verbatim the shape the verifier POSTED (the plain
    `line()` helper dumps ensure_ascii=False, whose bytes cannot even be
    encoded — the repro is about the wire form the door actually accepted)."""
    base = {"book_key": "kSur", "title": "Surrogat \ud800 bok",
            "authors": ["Aino A"], "read_year": 2024, "status": "read"}
    base.update(kw)
    return json.dumps(base)


@pytest.mark.parametrize("kw", [
    {"title": "Surrogat \ud800 bok"},
    {"book_key": "k\ud800"},
    {"date_read": "2024\ud800-01"},
    {"isbn13": "97891\ud800"},
    {"authors": ["Aina \ud800"]},
    {"genres": ["skönlitteratur \ud800"]},
], ids=["title", "book_key", "date_read", "isbn13", "author", "genre"])
def test_bundle_refuses_a_lone_surrogate_naming_the_line(authed, kw):
    """F-L2 (DA-verdict-c3, the surviving M7 plant): "\\ud800" is legal JSON,
    parse_bundle accepted it and the sqlite TEXT bind died with
    UnicodeEncodeError — NOT a sqlite3.Error, so it escaped the catch list as
    an HTTP 500, skipped conn.rollback() AND the cover unlink (verifier
    transcript .tmp/c3/FL2-repro-run1.log: 500 + orphan covers/1.jpg). The
    bind is strict utf-8, so the bind's vocabulary is the door's: the line
    400s naming itself and NOTHING stores."""
    tmp, client = authed
    r = client.post("/liselott/bundle", data=bundle_bytes(sur_line(**kw)),
                    content_type="application/octet-stream")
    assert r.status_code == 400, r.get_data(as_text=True)
    assert "rad 1" in r.get_data(as_text=True)
    assert stored_count(tmp) == 0


def test_the_lone_surrogate_repro_is_the_shape_it_claims(authed):
    """The guard must refuse the WIRE shape, not a Python convenience: the
    line really does carry a \\ud800 escape, really is valid JSON and really
    decodes to a lone surrogate — so a loosened guard dies here first."""
    raw = bundle_bytes(sur_line())
    assert b"\\ud800" in raw
    obj = json.loads(raw.decode("utf-8"))
    assert any(0xD800 <= ord(c) <= 0xDFFF for c in obj["title"])


# ── F-L3/F-M (c4): control bytes never reach a field, a row or a page ──────
@pytest.mark.parametrize("field,char", [
    ("title", "\x00"), ("title", "\x01"), ("title", "\x7f"),
    ("title", "\x1f"), ("title", "\t"), ("title", "\n"),
    ("book_key", "\x00"), ("isbn13", "\x00"), ("date_read", "\x00"),
    ("authors", "\x01"), ("genres", "\x00"),
], ids=["title-nul", "title-soh", "title-del", "title-us", "title-tab",
        "title-lf", "book_key-nul", "isbn-nul", "date-nul", "author-soh",
        "genre-nul"])
def test_bundle_refuses_control_characters_naming_the_field(authed, field,
                                                            char):
    """F-L3 + F-M (verifier c3: `a\x01b` and a NUL in a title were STORED with
    200 and reached the shelf markup). These fields are shaped — a title, an
    author, an ISBN, a date, a key — and none of them has a legitimate control
    character in its vocabulary, so the door refuses every C0/C1 (category
    Cc): the bind would otherwise carry it into served HTML. The refusal names
    the line AND the field, like every other refusal here."""
    tmp, client = authed
    kw = {"book_key": "kCtl", "title": "Styrtitel"}
    junk = {"title": f"Styrtitel {char} slut", "book_key": "k" + char,
            "isbn13": "9781234" + char, "date_read": "2024" + char,
            "authors": ["Aina A" + char],
            "genres": ["skönlitteratur" + char]}[field]
    kw[field] = junk
    r = client.post("/liselott/bundle", data=bundle_bytes(line(**kw)),
                    content_type="application/octet-stream")
    assert r.status_code == 400, r.get_data(as_text=True)
    body = r.get_data(as_text=True)
    assert "rad 1" in body and field in body
    assert "\x00" not in body          # names the code point, never the byte
    assert stored_count(tmp) == 0


def test_bundle_still_accepts_everyday_text(authed):
    """The guard's paired leg: the rule refuses control characters, NOT the
    alphabet. Swedish åäö, an emoji, a non-breaking space and a § stay legal —
    a rule that rejects the corpus it exists to serve is worse than the hole
    it closes."""
    tmp, client = authed
    r = client.post("/liselott/bundle", data=bundle_bytes(line(
        book_key="kOk", title="Även Åsa — Ö 2024 § 📚\u00a0",
        authors=["Joël Aït"], genres=["skönlitteratur"], read_year=2024)),
        content_type="application/octet-stream")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert stored_count(tmp) == 1


def test_seed_refuses_a_row_carrying_a_nul_naming_it(authed):
    """F-L3's /seed half (verifier .tmp/c3/FL3-repro-run1.log: the author name
    `Test\x00sson` imported with 200 and the NUL rode all the way into the
    shelf markup). The row is refused by its line number in the file, the byte
    is never echoed, and the F-C2 atomicity posture holds: the clean row
    beside it stores nothing either — one transaction, all or nothing."""
    tmp, client = authed
    r = client.post("/liselott/seed", data=(
        "## Lästa böcker 2024\n- 240101 Frisk bok av Aino A\n"
        "- 240102 Nollbok av Test\x00sson\n").encode(),
        content_type="application/octet-stream")
    assert r.status_code == 400, r.get_data(as_text=True)
    body = r.get_data(as_text=True)
    assert "rad 3" in body and "U+0000" in body
    assert "\x00" not in body
    assert "Ingen rad är importerad" in body
    assert stored_count(tmp) == 0


def test_seed_tab_form_row_is_still_the_overrides_path(authed):
    """The rule's own boundary: §5.4's tab-form author tail is FLAGGED (named,
    routed to import_overrides.csv), not refused as a control character — the
    separator the file format itself uses belongs to the row validator, so the
    answer still names the overrides file and never a U+0009."""
    tmp, client = authed
    r = client.post("/liselott/seed", data=(
        "## Lästa böcker 2024\n"
        "- 260101 Flaggad av Författare\tav\tTabbe T\n").encode(),
        content_type="application/octet-stream")
    assert r.status_code == 400
    body = r.get_data(as_text=True)
    assert "U+0009" not in body and "import_overrides.csv" in body


def test_served_pages_carry_no_control_bytes_after_an_import(authed):
    """F-M's measurement was BYTES on served pages, not responses: one NUL on
    each of the five pages the row reached. After the doors refuse the shapes,
    the same journey — import, shelf, home, detail, edit, search — paints zero
    NUL bytes, and a NUL posted straight into the detail field is refused."""
    tmp, client = authed
    assert client.post("/liselott/seed", data=(
        "## Lästa böcker 2024\n- 240101 Nollbok av Aino A\n").encode(),
        content_type="application/octet-stream").status_code == 200
    assert client.post("/liselott/bundle", data=bundle_bytes(
        line(book_key="kSida", title="Nollbok", isbn13="9781234567897")),
        content_type="application/octet-stream").status_code == 200
    for path in ("/liselott/bibliotek", "/liselott/", "/liselott/bok/1",
                 "/liselott/redigera/1", "/liselott/sok?q=Nollbok"):
        assert client.get(path).status_code == 200, path
        assert b"\x00" not in client.get(path).get_data(), path


def bomb_png() -> bytes:
    """A REAL PNG carrying a real bomb: valid signature + IHDR announcing
    20 000×20 000 px — 400 M px, over twice Pillow's guard limit — plus a
    stub IDAT. PIL's own DecompressionBombError fires while READING THE
    HEADER; the decode never starts (that is the guard's whole point), so
    the test is real and instant."""
    def chunk(tag, data):
        body = tag + data
        return (struct.pack(">I", len(data)) + body
                + struct.pack(">I", zlib.crc32(body)))
    ihdr = struct.pack(">IIBBBBB", 20_000, 20_000, 8, 0, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(b"\x00" * 100))
            + chunk(b"IEND", b""))


def test_bundle_decompression_bomb_cover_refused_naming_the_image(authed):
    """F-D2 leg 3 (shipped: 500 — DecompressionBombError is a plain
    Exception and the image refusal only caught
    UnidentifiedImageError/OSError/ValueError; the byte cap is no defence
    against pixel counts, 438 KB was enough). Now the bomb joins THE cover
    refusal (CoverRejected): Swedish copy, named line, 400, nothing
    stored, no file written."""
    tmp, client = authed
    r = client.post("/liselott/bundle", data=bundle_bytes(
        line(book_key="kBomb", title="Bombboken",
             cover_b64=base64.b64encode(bomb_png()).decode(),
             cover_source="openlibrary")),
        content_type="application/octet-stream")
    assert r.status_code == 400, r.get_data(as_text=True)
    text = r.get_data(as_text=True)
    assert "rad 1" in text and "omslag" in text.lower()
    assert stored_count(tmp) == 0
    assert not (tmp / "covers").is_dir() or list((tmp / "covers").glob("*")) == []


# ── F-E2: no Content-Length, no deal — the doors refuse to GUESS the body ───
def test_doors_refuse_a_body_they_cannot_measure_with_411(authed):
    """F-E2 (shipped: a POST whose envelope carries NO Content-Length —
    the chunked shape — reached the door with the app unable to bound
    what the transport never delimited: caps compared against nothing,
    and the door answered 200 about bytes it had not honestly seen).
    Both machine doors now answer 411 Length Required (named, Swedish
    copy) and import NOTHING — whatever the stream itself happens to
    carry. A normal client POST always carries Content-Length; this leg
    overrides wsgi.input WITHOUT it, exactly the F-E2 shape."""
    tmp, client = authed
    chunk = bundle_bytes(line(book_key="kChunk", title="Chunkbok"))
    for path in ("/liselott/bundle", "/liselott/seed"):
        r = client.post(path,
                        environ_overrides={"wsgi.input": io.BytesIO(chunk)},
                        headers={"Transfer-Encoding": "chunked"},
                        content_type="application/octet-stream")
        assert r.status_code == 411, (path, r.get_data(as_text=True))
        assert "Content-Length" in r.get_data(as_text=True), path
        assert stored_count(tmp) == 0, path
