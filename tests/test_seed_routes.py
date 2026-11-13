"""T6.4 — POST /seed and POST /bundle behind the owner session, the FULL
upsert matrix (PLAN-c3 §5.11 + the T6.4 (a)-(h) legs, F-1/F-7).

The plan's File line names app/seed.py + app/routes.py; the brief's file-
hygiene law (~250 target; seed.py already 341, routes.py 166+two views'
worth) moves the mechanism to app/bundle.py — the named-deviation pattern
s5 set with app/backfill.py. Behaviour is the plan verbatim:

  /seed    raw md body -> THE seed core (same functions the CLI runs), answers
           "parsed=725 stored=724 duplicates=1" (T8.5's literal, idempotent).
  /bundle  ndjson chunk -> upsert_bundle(): match ONLY on book_key; existing
           rows get holes-only fills (isbn13/isbn10/year/genres/cover),
           NEVER status/date_read/read_year/notes; a manual cover is never
           overwritten; a duplicate isbn13 is refused, reported in the
           conflicts array and the rest of that row's hole-fill still
           applies; > MAX_BUNDLE_CHUNK bytes -> 400 naming the byte budget
           BEFORE any parsing; a malformed line 400s naming the line number
           and rolls the WHOLE POST back; cover bytes go through THE one
           normalizer (store_cover). Response keys books/covers/inserted/
           updated/conflicts asserted verbatim. Both routes are in
           TOKENLESS_POSTS: no CSRF token, a foreign Origin still 400s, no
           session 302s. No seed token (F-7: the session IS the gate).
"""
import base64
import json
import sqlite3

import pytest

from app import create_app
from tests.test_add import COVER_FIXTURE
from tests.test_browse import PASSWORD

RAW_SEED = """# Liselotts lästa böcker 2015-2026 (konverterad)

## Lästa böcker 2026
- 260101 En bok av Aino A (betyg 5 i källan)
- 260202 Ljudboksboken av Bigga B (betyg 3 i källan)

## Lyssnade böcker 2025
- 250303 Gamla ljudboken av Cilla C

## Att läsa
- Framtida boken av Aino A
"""

B64 = base64.b64encode(COVER_FIXTURE.read_bytes()).decode()


def line(**kw):
    base = {"book_key": None, "title": "Titel", "authors": ["Aino A"],
            "date_read": None, "read_year": 2024, "format": "bok",
            "rating": None, "status": "read", "isbn13": None, "isbn10": None,
            "year": None, "genres": [], "cover_b64": None,
            "cover_source": None}
    base.update(kw)
    return json.dumps(base, ensure_ascii=False)


def bundle_bytes(*lines):
    return ("\n".join(lines) + "\n").encode("utf-8")


@pytest.fixture()
def authed(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    app = create_app()
    app.testing = True
    client = app.test_client()
    assert client.post("/liselott/satt-loesenord",
                       data={"loesenord": PASSWORD,
                             "bekrafta": PASSWORD}).status_code == 302
    return tmp_path, client


def rows(tmp):
    conn = sqlite3.connect(tmp / "liselott.db")
    try:
        return {r[0]: r for r in conn.execute(
            "SELECT book_key, title, status, isbn13, year, rating, notes,"
            " date_read, read_year, cover_source FROM book")}
    finally:
        conn.close()


# ── POST /seed — the seed core over HTTP (F-7: the session IS the gate) ─────
def test_seed_answers_the_counts_line_and_is_idempotent(authed):
    """T8.5's literal shape — parsed/stored/duplicates, correct counts for
    the body POSTed (here a synthetic 4-row corpus: 3 read + 1 wish), and a
    re-POST answers again without churn (idempotent, §6.6)."""
    tmp, client = authed
    r = client.post("/liselott/seed", data=RAW_SEED.encode("utf-8"),
                    content_type="application/octet-stream")
    assert r.status_code == 200
    import re
    assert re.fullmatch(r"parsed=4 stored=4 duplicates=0\n?",
                        r.get_data(as_text=True)), r.get_data(as_text=True)
    again = client.post("/liselott/seed", data=RAW_SEED.encode("utf-8"),
                        content_type="application/octet-stream")
    assert again.status_code == 200                       # idempotent (§6.6)
    conn = sqlite3.connect(tmp / "liselott.db")
    stored = conn.execute("SELECT COUNT(*) FROM book").fetchone()[0]
    conn.close()
    assert stored == 4                                    # 3 read + 1 wish


# ── POST /bundle — the upsert matrix ─────────────────────────────────────────
def _seed_existing(tmp, client):
    """One stored read book (key k1, holes everywhere) + a wish (key k2)."""
    client.post("/liselott/seed", data=(
        "## Lästa böcker 2024\n- 240101 Hålboken av Aino A\n\n"
        "## Att läsa\n- Önskan av Cilla C\n").encode("utf-8"),
        content_type="application/octet-stream")


def test_bundle_fills_holes_never_transitions(authed):
    """(a)+(b)+(c): an existing book gets ONLY NULL/empty holes filled —
    isbn13/isbn10/year/genres — and a posted status/read_year/date_read
    change is SILENTLY ignored (status flip wishlist→read must not apply to
    anything, and read_year never moves; the seed core's own read_year IS
    kept)."""
    tmp, client = authed
    _seed_existing(tmp, client)
    # the real legs on the ACTUAL keys the seed produced:
    stored = rows(tmp)
    key_hal = next(k for k, r in stored.items() if r[1] == "Hålboken")
    key_on = next(k for k, r in stored.items() if r[1] == "Önskan")
    r = client.post(
        "/liselott/bundle", data=bundle_bytes(
            line(book_key=key_hal, title="Hålboken",
                 isbn13="9789100000001", isbn10="9100000001", year=2024,
                 genres=["Roman"], status="wishlist", read_year=1999,
                 date_read="1999-01-01"),
            line(book_key=key_on, title="Önskan", status="read",
                 read_year=2001, date_read="2001-01-01")),
        content_type="application/octet-stream")
    assert r.status_code == 200
    after = rows(tmp)
    hal = after[key_hal]
    assert hal[3] == "9789100000001"                 # isbn filled
    assert hal[5] is None                            # rating: not a fill key
    assert hal[2] == "read"                          # status NEVER changes
    assert hal[8] == 2024                            # read_year untouched
    assert hal[7] == "2024-01-01"                    # date_read untouched
    on = after[key_on]
    assert on[2] == "wishlist"                       # wish stays a wish
    assert on[8] == 0 and on[7] is None              # sentinel/date untouched
    conn = sqlite3.connect(tmp / "liselott.db")
    genres = [g for (g,) in conn.execute(
        "SELECT g.name FROM genre g JOIN book_genre bg ON bg.genre_id = g.id"
        " JOIN book b ON b.id = bg.book_id WHERE b.book_key = ?", (key_hal,))]
    conn.close()
    assert genres == ["Roman"]                       # genres filled (hole)


def test_bundle_inserts_new_rows_as_is(authed):
    """New book_key: status as-is from the line (a WISHLINE lands 'wishlist'
    with its read_year 0 sentinel from §5.11's wish export), cover written."""
    tmp, client = authed
    _seed_existing(tmp, client)
    r = client.post("/liselott/bundle", data=bundle_bytes(
        line(book_key="k-new", title="Ny bok", status="wishlist",
             read_year=0, cover_b64=B64, cover_source="openlibrary"),
        line(book_key="k-new2", title="Ny läs bok", status="read",
             read_year=2023, rating=4, date_read="2023-05-05")),
        content_type="application/octet-stream")
    assert r.status_code == 200
    j = r.get_json()
    assert j["inserted"] == 2 and j["covers"] == 1
    assert j["books"] == 4                           # total book rows now
    assert j["updated"] == 0 and j["conflicts"] == []
    after = rows(tmp)
    assert after["k-new"][2] == "wishlist" and after["k-new"][8] == 0
    assert after["k-new2"][2] == "read"
    conn = sqlite3.connect(tmp / "liselott.db")
    cp = conn.execute("SELECT cover_path, cover_source FROM book"
                      " WHERE book_key = 'k-new'").fetchone()
    conn.close()
    assert cp == (f"covers/{_id_of(tmp, 'k-new')}.jpg", "openlibrary")
    assert (tmp / cp[0]).exists()                    # bytes really landed


def _id_of(tmp, key):
    conn = sqlite3.connect(tmp / "liselott.db")
    try:
        return conn.execute("SELECT id FROM book WHERE book_key = ?",
                            (key,)).fetchone()[0]
    finally:
        conn.close()


def test_bundle_cover_never_overwrites_manual(authed):
    """(h): a stored 'manual' cover is untouched — neither the file nor the
    columns. The provider-sourced cover may be refreshed (only-manual is the
    never rule); with no cover at all the bundle's bytes land via THE
    store_cover normalizer."""
    tmp, client = authed
    _seed_existing(tmp, client)
    stored = rows(tmp)
    key_hal = next(k for k, r in stored.items() if r[1] == "Hålboken")
    hid = _id_of(tmp, key_hal)
    (tmp / "covers").mkdir(exist_ok=True)
    (tmp / "covers" / f"{hid}.jpg").write_bytes(b"MANUAL-BYTES")
    conn = sqlite3.connect(tmp / "liselott.db")
    conn.execute("UPDATE book SET cover_path = ?, cover_source = 'manual'"
                 " WHERE id = ?", (f"covers/{hid}.jpg", hid))
    conn.commit()
    conn.close()
    client.post("/liselott/bundle", data=bundle_bytes(
        line(book_key=key_hal, title="Hålboken", cover_b64=B64,
             cover_source="googlebooks")),
        content_type="application/octet-stream")
    conn = sqlite3.connect(tmp / "liselott.db")
    cp = conn.execute("SELECT cover_path, cover_source FROM book"
                      " WHERE id = ?", (hid,)).fetchone()
    conn.close()
    assert cp == (f"covers/{hid}.jpg", "manual")     # NEVER overwritten
    assert (tmp / "covers" / f"{hid}.jpg").read_bytes() == b"MANUAL-BYTES"


def test_bundle_duplicate_isbn_refused_and_reported(authed):
    """(d): row B carries an isbn13 already owned by row A (different
    book_key) — the ISBN is NOT applied, the row appears in the conflicts
    array {"book_key":…, "reason":"duplicate isbn"}, and the rest of B's
    hole-fill STILL applies. First writer wins (A keeps its isbn)."""
    tmp, client = authed
    client.post("/liselott/bundle", data=bundle_bytes(
        line(book_key="kA", title="Bok A", isbn13="9789100000009"),
        line(book_key="kB", title="Bok B", isbn13="9789100000009",
             year=2022)), content_type="application/octet-stream")
    after = rows(tmp)
    assert after["kA"][3] == "9789100000009"
    assert after["kB"][3] is None                    # isbn refused…
    assert after["kB"][4] == 2022                    # …year hole still filled


def test_bundle_duplicate_conflict_shape_and_count(authed):
    """The same POST as the leg above, response-side: conflicts is an ARRAY
    of {"book_key","reason"} and conflicts count matches (§5.11 verbatim
    reason string)."""
    tmp, client = authed
    r = client.post("/liselott/bundle", data=bundle_bytes(
        line(book_key="kA", title="Bok A", isbn13="9789100000009"),
        line(book_key="kB", title="Bok B", isbn13="9789100000009"),
        line(book_key="kC", title="Bok C", isbn13="9789100000009")),
        content_type="application/octet-stream")
    j = r.get_json()
    assert j["conflicts"] == [{"book_key": "kB", "reason": "duplicate isbn"},
                              {"book_key": "kC", "reason": "duplicate isbn"}]
    assert j["inserted"] == 3 and j["covers"] == 0


def test_bundle_rerun_is_idempotent_zero_everything(authed):
    """(e): re-POST the SAME chunk → updated 0 (no holes left), covers 0 (no
    new bytes — the stored file already holds the exact row's b64), inserted
    0. The T8.6 loop re-POSTs nothing, but a POST must never churn."""
    tmp, client = authed
    chunk = bundle_bytes(line(book_key="k1", title="Första",
                              isbn13="9789100000002", year=2020,
                              cover_b64=B64, cover_source="openlibrary"))
    first = client.post("/liselott/bundle", data=chunk,
                        content_type="application/octet-stream").get_json()
    again = client.post("/liselott/bundle", data=chunk,
                        content_type="application/octet-stream").get_json()
    assert first["inserted"] == 1 and first["covers"] == 1
    assert again == {**first, "inserted": 0, "updated": 0, "covers": 0}


def test_bundle_over_cap_refused_naming_the_budget(authed):
    """(f): MAX_BUNDLE_CHUNK (900 000, P1-1 re-pin) — the 400 arrives BEFORE
    any parsing, naming the byte budget in Swedish."""
    tmp, client = authed
    fat = b"x" * 900_001
    r = client.post("/liselott/bundle", data=fat,
                    content_type="application/octet-stream")
    assert r.status_code == 400
    text = r.get_data(as_text=True)
    assert "900000" in text and "900001" in text
    conn = sqlite3.connect(tmp / "liselott.db")
    assert conn.execute("SELECT COUNT(*) FROM book").fetchone()[0] == 0
    conn.close()


def test_bundle_malformed_line_rolls_back_naming_the_line(authed):
    """(g): the THIRD line is broken JSON → 400 naming line 3 and NOTHING
    imported — not even the two good lines before it."""
    tmp, client = authed
    bad = (line(book_key="k1", title="Bra ett") + "\n"
           + line(book_key="k2", title="Bra två") + "\n"
           + "{not json at all\n").encode("utf-8")
    r = client.post("/liselott/bundle", data=bad,
                    content_type="application/octet-stream")
    assert r.status_code == 400
    assert "3" in r.get_data(as_text=True)           # the line number, named
    conn = sqlite3.connect(tmp / "liselott.db")
    assert conn.execute("SELECT COUNT(*) FROM book").fetchone()[0] == 0
    conn.close()


def test_bundle_keyless_line_is_malformed(authed):
    """book_key is THE match key (§5.11) — a line without it names the line
    and rolls back, it is never matched by title."""
    tmp, client = authed
    r = client.post("/liselott/bundle",
                    data=b'{"title": "Utan nyckel"}\n',
                    content_type="application/octet-stream")
    assert r.status_code == 400
    assert "1" in r.get_data(as_text=True)
    conn = sqlite3.connect(tmp / "liselott.db")
    assert conn.execute("SELECT COUNT(*) FROM book").fetchone()[0] == 0
    conn.close()


# ── the machine-route posture (§6.6 + F-7) ───────────────────────────────────
def test_bundle_end_to_end_through_the_real_exporter(tmp_path, monkeypatch):
    """The plan's T6.4 step-1 wording: the §5.11 contract tested END-TO-END
    through the REAL scripts/export_bundle.py — build-side DB enriched
    (isbn/year/genres + a store_cover cover), exported, and the export's own
    bytes POSTed to the bare production shelf: holes fill through the real
    exporter's line shape, the cover lands under the production row's id,
    and a book absent from the bundle is untouched with its cover NULL
    (leg c). This is the leg no hand-written line can fake."""
    from app import db as dbmod, seed
    from scripts.export_bundle import main as export_main

    build = tmp_path / "build"
    build.mkdir()
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(build))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    prod = tmp_path / "prod"
    key = seed.book_key("En bok", ["Aino A"])

    conn2 = sqlite3.connect(build / "liselott.db")
    dbmod.init_db(conn2)
    now = "2026-11-13T00:00:00Z"
    cur = conn2.execute(
        "INSERT INTO book (title, format, date_read, read_year, rating,"
        " status, book_key, isbn13, year, created, updated)"
        " VALUES ('En bok','bok','2026-01-01',2026,5,'read',?,"
        " '9789100000042',2020,?,?)", (key, now, now))
    seed.set_authors(conn2, cur.lastrowid, ["Aino A"])
    conn2.execute("INSERT INTO genre (name) VALUES ('Roman')")
    conn2.execute("INSERT INTO book_genre (book_id, genre_id) VALUES (1,1)")
    from app import enrich
    build_id = cur.lastrowid
    enrich.store_cover(conn2, build_id, COVER_FIXTURE.read_bytes(),
                       "openlibrary")
    build_cover = (build / "covers" / f"{build_id}.jpg").read_bytes()
    assert export_main(["--out", str(tmp_path / "b.jsonl")]) == 0
    conn2.close()

    # production boots BARE (same seed md, no enrichment) — then the real
    # exporter's bytes travel:
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(prod))
    app = create_app()
    app.testing = True
    client = app.test_client()
    assert client.post("/liselott/satt-loesenord",
                       data={"loesenord": PASSWORD,
                             "bekrafta": PASSWORD}).status_code == 302
    client.post("/liselott/seed", data=RAW_SEED.encode("utf-8"),
                content_type="application/octet-stream")
    r = client.post("/liselott/bundle",
                    data=(tmp_path / "b.jsonl").read_bytes(),
                    content_type="application/octet-stream")
    assert r.status_code == 200
    j = r.get_json()
    assert j["inserted"] == 0 and j["covers"] == 1 and j["conflicts"] == []
    assert j["updated"] == 1 and j["books"] == 4     # 1 filled, 3 untouched

    conn = sqlite3.connect(prod / "liselott.db")
    row = conn.execute("SELECT id, isbn13, year, cover_path, cover_source"
                       " FROM book WHERE book_key = ?", (key,)).fetchone()
    untouched = conn.execute(
        "SELECT status, cover_path FROM book WHERE book_key != ?",
        (key,)).fetchall()
    genres = conn.execute(
        "SELECT g.name FROM genre g JOIN book_genre bg ON bg.genre_id = g.id"
        " JOIN book b ON b.id = bg.book_id WHERE b.book_key = ?",
        (key,)).fetchall()
    conn.close()
    assert row[1] == "9789100000042" and row[2] == 2020
    assert row[3] == f"covers/{row[0]}.jpg"           # the PRODUCTION id
    assert row[4] == "openlibrary"
    assert (prod / row[3]).read_bytes() == enrich.normalize_image(
        build_cover)   # production's bytes = THE normalizer applied to the
                       # bundle's bytes (JPEG re-encode is not a fixed point,
                       # so the truth is one normalization of what travelled)
    assert genres == [("Roman",)]
    # (leg c) every book absent from the bundle is untouched, cover NULL:
    assert len(untouched) == 3 and all(c is None for _, c in untouched)


def test_no_session_no_entry(authed):
    """Unauthenticated POSTs 302 to login (the guard's allow-list is four
    paths; the seed token is GONE — F-7: no unauthenticated door, not even
    one-time)."""
    tmp, _ = authed
    anon = create_app().test_client()
    for path in ("/liselott/seed", "/liselott/bundle"):
        r = anon.post(path, data=b"{}")
        assert r.status_code == 302, path
        assert r.headers["Location"] == "/liselott/logga-in", path


def test_foreign_origin_still_400s_without_a_token(authed):
    """TOKENLESS ≠ GUARDLESS (P2-r4): no CSRF token is needed, a foreign
    Origin is still the §6.6 400."""
    _, client = authed
    r = client.post("/liselott/bundle", data=b"{}",
                    headers={"Origin": "http://evil.example"})
    assert r.status_code == 400
    r = client.post("/liselott/seed", data=b"",
                    headers={"Origin": "http://evil.example"})
    assert r.status_code == 400


def test_same_origin_and_bare_curl_pass_without_token(authed):
    """The T8.5/T8.6 runbook shape survives: bare curl (no Origin, no token)
    and same-origin both reach the route TOKENLESS. (F-E2, MC 12451: the
    empty chunk now travels as a body of ONE newline with its honest
    Content-Length — a POST whose envelope carries NO length is a 411 at
    the door, so the old no-length shape is deliberately retired here.)"""
    _, client = authed
    host = "localhost"
    assert client.post("/liselott/bundle", data=b"\n").status_code == 200
    assert client.post("/liselott/bundle", data=b"\n",
                       headers={"Origin": f"http://{host}"}).status_code == 200


# ── P3-4 (MC 12451): named 4xx on owner input — never a 500, never silent ──
def stored_count(tmp):
    conn = sqlite3.connect(tmp / "liselott.db")
    try:
        return conn.execute("SELECT COUNT(*) FROM book").fetchone()[0]
    finally:
        conn.close()


def test_seed_malformed_utf8_400_naming_the_coding(authed):
    """P3-4 leg 1: the shipped answer was a 500 (UnicodeDecodeError escaped
    the route). Now 400 NAMING "otillräcklig kodning", nothing stored."""
    tmp, client = authed
    r = client.post("/liselott/seed",
                    data=b"## L\xe4sta b\xf6cker 2026\n- 260101 Boken"
                         b" av Aino A\n",             # broken utf-8 bytes
                    content_type="application/octet-stream")
    assert r.status_code == 400
    assert "otillräcklig kodning" in r.get_data(as_text=True)
    assert stored_count(tmp) == 0


def test_seed_unknown_section_400_naming_it(authed):
    """P3-4 leg 2: an unrecognised '## ' header 500s on the shipped code
    (ValueError escapes seed.parse_file). Now 400 naming the section,
    nothing stored."""
    tmp, client = authed
    r = client.post("/liselott/seed", data=(
        "## Snidade b\xf6cker 2026\n- 260101 Noken av Aino A\n").encode(),
        content_type="application/octet-stream")
    assert r.status_code == 400
    text = r.get_data(as_text=True)
    assert "## Snidade böcker 2026" in text          # THE section, named
    assert stored_count(tmp) == 0


def test_seed_one_flagged_row_commits_nothing(authed):
    """F-C2 (DA-verdict-c2, MC 12451): the shipped door answered 400 AFTER
    COMMITTING the same body's clean rows (measured 6→7) — one door, two
    postures, while its three sibling 400s all say "Ingen rad är
    importerad". Here one §5.4-flagged row (tab-form av-tail) stands beside
    one clean row: the flagged title is still NAMED in the 400, the copy
    now says what the door does, and the clean row did NOT land either —
    the count proves nothing committed."""
    tmp, client = authed
    r = client.post("/liselott/seed", data=(
        "## Lästa böcker 2026\n"
        "- 260101 Flaggad av Författare\tav\tTabbe T\n"
        "- 260202 Rena rader av Aino A\n").encode("utf-8"),
        content_type="application/octet-stream")
    assert r.status_code == 400
    text = r.get_data(as_text=True)
    assert "Flaggad" in text                           # the flagged row, named
    assert "Ingen rad är importerad" in text           # copy = behaviour
    assert stored_count(tmp) == 0                      # clean row NOT stored


def test_seed_over_one_mebibyte_413_naming_the_budget(authed):
    """P3-4 leg 3: /seed accepted ANY size on the shipped code (the 900 000
    rule was /bundle-only; only the lane edge 413s). The app now caps at
    1 MiB itself, /bundle's idiom: 413 BEFORE any parsing, budget named."""
    tmp, client = authed
    r = client.post("/liselott/seed", data=b"x" * 1_048_577,
                    content_type="application/octet-stream")
    assert r.status_code == 413
    text = r.get_data(as_text=True)
    assert "1048576" in text and "1048577" in text
    assert stored_count(tmp) == 0


def test_bundle_rating_outside_1_5_400_naming_the_line(authed):
    """P3-4 leg 4: rating:99 was a 500 (the book.rating CHECK refused,
    unhandled, inside upsert). Now the §5.11-(g) posture on domain errors
    too: 400 naming the 1-based line, nothing written."""
    tmp, client = authed
    r = client.post("/liselott/bundle", data=bundle_bytes(
        line(book_key="kR", title="Betygshäftet", rating=99)),
        content_type="application/octet-stream")
    assert r.status_code == 400
    assert "rad 1" in r.get_data(as_text=True)
    assert stored_count(tmp) == 0


def test_bundle_new_row_without_title_400_naming_the_line(authed):
    """P3-4 leg 5: a NEW book_key line without title 500s (KeyError inside
    _store_new). 400 naming the line now; the merge path never reads title,
    so title stays optional for existing keys (§5.11's match key is the
    book_key, not the title)."""
    tmp, client = authed
    r = client.post("/liselott/bundle",
                    data=b'{"book_key": "keyno-title", "read_year": 2024}\n',
                    content_type="application/octet-stream")
    assert r.status_code == 400
    assert "rad 1" in r.get_data(as_text=True)
    assert stored_count(tmp) == 0


def test_bundle_domain_error_mid_file_rolls_back_every_row(authed):
    """The rollback proof P3-4 demands: line 1 is a FULL valid row (cover
    bytes included — store_cover must not commit mid-chunk), line 2 is the
    domain error, line 3 would be valid again. 400 names rad 2 and the row
    count is UNCHANGED — not line 1, not line 3."""
    tmp, client = authed
    r = client.post("/liselott/bundle", data=bundle_bytes(
        line(book_key="kA", title="Först", isbn13="9789100000021",
             cover_b64=B64, cover_source="openlibrary"),
        line(book_key="kB", title="Fusk", rating=99),
        line(book_key="kC", title="Sist")),
        content_type="application/octet-stream")
    assert r.status_code == 400
    assert "rad 2" in r.get_data(as_text=True)
    assert stored_count(tmp) == 0
    again = client.post("/liselott/bundle", data=bundle_bytes(
        line(book_key="kA", title="Först", isbn13="9789100000021"),
        line(book_key="kC", title="Sist")),
        content_type="application/octet-stream")
    assert again.status_code == 200                   # the DB took nothing
    assert again.get_json()["inserted"] == 2
