"""T6.4 — POST /seed and POST /bundle: the HTTP ingest doors (F-1/F-7).

Two routes, one rule set (§5.11 + the T6.4 (a)-(h) matrix). The plan's File
line names app/seed.py + app/routes.py; the brief's file-hygiene law (seed.py
was already 341 lines when M6 opened) moves the mechanism HERE — the named-
deviation pattern app/backfill.py set in M5. Behaviour is the plan verbatim:

* /seed    — raw md body through THE seed core (`seed.load`, the exact
             functions data-import/import_seed.py runs; the repo's alias and
             override CSVs travel with it — no second seed path, F-7).
             Answers the "parsed=… stored=… duplicates=…" line T8.5 pins;
             idempotent (§6.6). A validator-flagged row 400s naming the
             titles — the CLI's exit-2 posture, never a silent skip.
* /bundle  — an ndjson chunk through `parse_bundle` + `upsert_bundle`.

The merge (§5.11, binding): match ONLY on book_key; an existing row gets
holes-only fills (isbn13, isbn10, year when NULL; genres when it has none;
cover when it has none) and NEVER a transition — status, date_read, read_year
and notes are untouchable by a bundle (leg a/b: a status flip in the line is
silently ignored). A stored admin cover ('manual', plus 'manual-url' — the
OQ-2 door, enrich.MANUAL_COVER_SOURCES) is never overwritten (leg h). A line
carrying an isbn13 another row already owns gets that ISBN refused and the
row reported in `conflicts` as {"book_key":…,"reason":"duplicate isbn"}; the
rest of its hole-fill still applies (leg d, first writer wins). Cover bytes
land through THE one normalizer (enrich.store_cover, P1-2) — and re-POSTing
a chunk whose cover bytes are already byte-identical on disk writes NOTHING
(leg e's "no new cover bytes"), which is exactly what reconciles (e)'s zero
with (h)'s never-manual: idempotence is measured in BYTES, not in POSTs.

Body > MAX_BUNDLE_CHUNK bytes 400s BEFORE any parsing, naming the byte
budget (900 000 — the P1-1 lane cap, re-pinned from §5.11's 900 KB); a
malformed line 400s naming its 1-based line number with the WHOLE POST
rolled back: every line — JSON, book_key, value vocabulary, cover base64 and
image bytes — is validated in `parse_bundle` BEFORE `upsert_bundle` writes
anything (leg g). What parse cannot see — a line the DB itself refuses
(rating outside the CHECK, a new row without its title) — 400s from the
SAME named-line path via a per-line catch in the upsert loop (P3-4,
MC 12451), still rolling the whole POST back: the loop is ONE transaction
(store_cover lands its row-update commit=False), so a refusal mid-file
imports NOTHING.

Both doors sit in auth.TOKENLESS_POSTS (the §6.6 machine trio's vocabulary):
no CSRF token, but a foreign Origin still 400s (P2-r4) and no session still
302s — and there is NO seed token (F-7: the owner session IS the gate, in
every state; the plan retires the one-time door).
"""
import base64
import json
import sqlite3
import tempfile
from pathlib import Path

from flask import jsonify, request

from app import REPO_ROOT, auth, db, enrich, seed

MAX_BUNDLE_CHUNK = 900_000          # §5.11 re-pinned by P1-1: refuse larger
MAX_SEED_BODY = 1_048_576           # 1 MiB, /seed's own cap (P3-4, MC 12451):
                                    # §5.11/P1-1's "no route accepts a bigger
                                    # body" survived production only because
                                    # the lane edge 413s >1 MiB — the APP owns
                                    # its budget, /bundle's idiom, 413-named
LENGTH_REQUIRED = (
    "Innehållets längd (Content-Length) saknas — dörren vägrar gissa sig "
    "till vad transporten skickade: skicka chunken igen med längden i "
    "höljet. Ingen rad är importerad")   # F-E2 (MC 12451), see the doors
SEED_ALIASES = REPO_ROOT / "data-import" / "author_aliases.csv"
SEED_OVERRIDES = REPO_ROOT / "data-import" / "import_overrides.csv"


class BundleError(Exception):
    """A line the §5.11 contract refuses — carries the 1-based line number
    and the Swedish reason; the route 400s with both, nothing written."""

    def __init__(self, line, reason):
        super().__init__(f"rad {line}: {reason}")
        self.line, self.reason = line, reason


def parse_bundle(raw: bytes) -> list[dict]:
    """ndjson bytes -> validated dicts, EVERY line before anything writes
    (leg g's rollback guarantee). Raises BundleError on the first refusal."""
    lines, seen = [], set()
    for n, chunk in enumerate(raw.split(b"\n"), start=1):
        if not chunk.strip():
            continue
        try:
            obj = json.loads(chunk)
        except ValueError as e:
            raise BundleError(n, f"förväntades ett JSON-objekt per rad ({e})")
        if not isinstance(obj, dict) or not obj.get("book_key"):
            raise BundleError(n, "book_key saknas — den är upptagsnyckeln "
                                 "(§5.11); titel matchar aldrig")
        if obj.get("status") not in (None, "read", "wishlist"):
            raise BundleError(n, f"okänd status {obj['status']!r}")
        rating = obj.get("rating")
        if rating is not None and (isinstance(rating, bool)
                                   or not isinstance(rating, int)
                                   or not 1 <= rating <= 5):
            # P3-4 leg 4: the book.rating CHECK refused this with a 500;
            # the value domain belongs to the vocabulary parse already owns.
            raise BundleError(n, f"betyg {rating!r} är utanför 1–5 — ska "
                                 "vara ett heltal 1–5 eller tomt")
        read_year = obj.get("read_year")
        if read_year is not None and (
                isinstance(read_year, bool) or not isinstance(read_year, int)
                or not (read_year == 0 or 1000 <= read_year <= 9999)):
            # F-A2 (a, MC 12451): the INTEGER column has affinity, NOT
            # constraint — "okänt-2025" landed as TEXT and the shelf sort
            # died on it (home page 500 until a DB repair). The year joins
            # the vocabulary parse already owns; 0 is the §5.11 wishline
            # sentinel, a real year is the four digits the seed's own
            # section regex (\d{4}) has always required.
            raise BundleError(n, f"read_year {read_year!r} är inget giltigt "
                                 "år — ett heltal med fyra siffror, 0 eller "
                                 "tomt")
        # F-A2(a)+F-D2+F-G2 (MC 12451): ONE vocabulary pass for every scalar
        # the line carries, beside the year refusal it grew out of. The
        # INTEGER columns have affinity, not constraint; the dup-check
        # HASHES book_key (an unhashable list raised TypeError right here —
        # F-D2 leg 1, outside every handler); the INSERT binds die on
        # containers (InterfaceError — F-D2 leg 2); and set_authors/
        # _fill_genres iterate a bare string into single-character garbage
        # (F-G2). One loop refuses all of it THERE with the named-line 400
        # the door already answers for rating/status/cover_source — "fix
        # once, not per family" (DA-verdict-c2 F-D2). Formats stay with
        # their owners: status/cover_source/rating keep their own checks.
        for field in ("book_key", "title", "date_read", "isbn13", "isbn10"):
            value = obj.get(field)
            if value is not None and not isinstance(value, str):
                raise BundleError(n, f"fältet {field} ska vara text eller "
                                     f"tomt, inte {type(value).__name__}")
        for field in ("year",):
            value = obj.get(field)
            if value is not None and (isinstance(value, bool)
                                      or not isinstance(value, int)
                                      or not 1000 <= value <= 9999):
                raise BundleError(n, f"year {value!r} är inget giltigt "
                                     "utgivningsår — ett heltal med fyra "
                                     "siffror eller tomt")
        for field in ("authors", "genres"):
            value = obj.get(field)
            if value is not None and (
                    not isinstance(value, list)
                    or not all(isinstance(v, str) for v in value)):
                raise BundleError(n, f"fältet {field} ska vara en lista av "
                                     f"texter, inte {value!r}")
        if obj.get("cover_source") not in (
                None, "libris", "googlebooks", "openlibrary", "manual",
                "manual-url"):
            raise BundleError(n, f"okänd cover_source {obj['cover_source']!r}")
        if obj["book_key"] in seen:
            raise BundleError(n, f"book_key {obj['book_key']!r} comes twice "
                                 "in one chunk — a chunk stays idempotent")
        seen.add(obj["book_key"])
        if obj.get("cover_b64") is not None:
            obj["_cover_bytes"] = _cover_bytes(n, obj)
        lines.append(obj)
    return lines


def _cover_bytes(n, obj) -> bytes:
    """Decode + image-validate NOW (the parse phase), so a broken cover line
    fails the whole POST while nothing is written — and so bytes can only
    reach disk through store_cover, THE normalizer."""
    try:
        data = base64.b64decode(obj["cover_b64"], validate=True)
    except Exception as e:
        raise BundleError(n, f"cover_b64 går inte att avkodas: {e}")
    try:
        enrich.validate_cover_bytes(data)
    except enrich.CoverRejected as e:
        raise BundleError(n, f"omslaget duger inte: {e}")
    return data


def _isbn_owner(conn, value, book_key):
    """The first-writer rule (§5.11): another row — any key but this line's —
    already carries this ISBN in either column. The schema has no UNIQUE on
    isbn13 on purpose: the RULE is this lookup, not a constraint."""
    return conn.execute(
        "SELECT 1 FROM book WHERE book_key != ?"
        " AND (isbn13 = ? OR isbn10 = ?) LIMIT 1",
        (book_key, value, value)).fetchone() is not None


def _fill_genres(conn, book_id, names) -> bool:
    """Genres join the hole vocabulary: filled only when the row has NONE
    (T6.4 leg c: genres is a fill, not a replace)."""
    if not names:
        return False
    for name in names:
        conn.execute("INSERT OR IGNORE INTO genre (name) VALUES (?)", (name,))
        gid = conn.execute("SELECT id FROM genre WHERE name = ?",
                           (name,)).fetchone()[0]
        conn.execute("INSERT OR IGNORE INTO book_genre (book_id, genre_id)"
                     " VALUES (?,?)", (book_id, gid))
    return True


def _store_new(conn, obj, now, new_covers):
    """A book_key the DB never saw lands AS-IS (§5.11): status/read_year/
    date_read/rating/format exactly as exported — a wishline keeps its
    read_year 0 sentinel, a read row its date. The only refusal an INSERT
    can hit is the ISBN first-writer rule: then the row still lands, ISBN
    less, and this returns its conflict. Returns (conflict, cover_written);
    the cover's rel path joins `new_covers` BEFORE the write, so the
    caller's rollback can unlink a written-but-rejected file (F-B2/F-K) —
    the row it belonged to is going away with it, so the file is an orphan
    by then, never a live reference. commit=False (P3-4) keeps the
    row-update in the POST's one transaction."""
    fmt = obj.get("format") if obj.get("format") in ("bok", "ljudbok") else "bok"
    isbn = obj.get("isbn13")
    conflict = bool(isbn) and _isbn_owner(conn, isbn, obj["book_key"])
    cur = conn.execute(
        "INSERT INTO book (title, format, date_read, read_year, rating,"
        " notes, status, book_key, isbn13, isbn10, year, created, updated)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (obj["title"], fmt, obj.get("date_read"),
         obj.get("read_year") if obj.get("read_year") is not None else 0,
         obj.get("rating"), None, obj.get("status") or "read",
         obj["book_key"], None if conflict else isbn, obj.get("isbn10"),
         obj.get("year"), now, now))
    book_id = cur.lastrowid
    seed.set_authors(conn, book_id, obj.get("authors") or [])
    _fill_genres(conn, book_id, obj.get("genres"))
    written = False
    if obj.get("_cover_bytes") is not None:
        # a fresh row has no file yet — the write always lands (counted in
        # BYTES, not POSTs; leg e's zero belongs to the MERGE path below)
        new_covers.append(f"{enrich.COVER_SUBDIR}/{book_id}.jpg")
        enrich.store_cover(conn, book_id, obj["_cover_bytes"],
                           obj.get("cover_source") or "openlibrary",
                           commit=False)          # one transaction (P3-4)
        written = True
    return conflict, written


def _merge_into(conn, state_dir, row, obj):
    """Holes only, never transitions (§5.11 binding). The obj gains the
    flags _touched/_cover_written; returns whether an ISBN was refused."""
    (book_id, isbn13, isbn10, year, cover_path, cover_source) = row
    touched, conflict = False, False
    now = auth.utcnow_iso()
    for field, stored, value in (("isbn13", isbn13, obj.get("isbn13")),
                                ("isbn10", isbn10, obj.get("isbn10"))):
        if not value or stored:
            continue                          # not a hole — never overwrite
        if _isbn_owner(conn, value, obj["book_key"]):
            conflict = True                   # refused; the rest still fills
            continue
        conn.execute(f"UPDATE book SET {field} = ?, updated = ?"
                     " WHERE id = ?", (value, now, book_id))
        touched = True
    if year is None and obj.get("year"):
        conn.execute("UPDATE book SET year = ?, updated = ? WHERE id = ?",
                     (obj["year"], now, book_id))
        touched = True
    if not conn.execute("SELECT 1 FROM book_genre WHERE book_id = ? LIMIT 1",
                        (book_id,)).fetchone():
        touched = _fill_genres(conn, book_id, obj.get("genres")) or touched
    data = obj.get("_cover_bytes")
    if data is not None and cover_source not in enrich.MANUAL_COVER_SOURCES:
        # no cover, or a PROVIDER cover — the bundle's bytes may land; the
        # owner's own (manual/manual-url) never, not even "upgraded" (leg h).
        # Counted in BYTES, not POSTs (leg e): normalize first, compare, and
        # a re-POST whose bytes already sit on disk churns nothing.
        current = (state_dir / cover_path).read_bytes() if cover_path \
            and (state_dir / cover_path).exists() else None
        if current != enrich.normalize_image(data):
            enrich.store_cover(conn, book_id, data,
                               obj.get("cover_source") or "openlibrary",
                               commit=False)      # one transaction (P3-4)
            obj["_cover_written"] = True
            touched = True
    obj["_touched"] = touched
    return conflict


def upsert_bundle(conn, state_dir, lines) -> dict:
    """The §5.11 merge, ONE transaction per POST — and ONE rollback that
    reaches the bytes too (F-B2/F-K, MC 12451): a line the DB refuses, a
    KeyError, or a cover write the disk refuses raises the SAME BundleError
    the parse phase uses, named by 1-based line; the loop's transaction is
    rolled BACK (store_cover lands commit=False, so no commit ever landed
    mid-file) and the cover files the rejected lines had already written are
    unlinked — after the rollback no row references them, they are orphans.
    Response keys the T6.4 DoD pins verbatim: books / covers / inserted /
    updated / conflicts."""
    report = {"covers": 0, "inserted": 0, "updated": 0, "conflicts": []}
    new_covers: list[str] = []
    try:
        for n, obj in enumerate(lines, start=1):
            try:
                row = conn.execute(
                    "SELECT id, isbn13, isbn10, year, cover_path, cover_source"
                    " FROM book WHERE book_key = ?", (obj["book_key"],)).fetchone()
                if row is None:
                    conflict, written = _store_new(conn, obj, auth.utcnow_iso(),
                                                   new_covers)
                    report["inserted"] += 1
                    report["covers"] += 1 if written else 0
                else:
                    conflict = _merge_into(conn, state_dir, row, obj)
                    report["updated"] += 1 if obj.pop("_touched", False) else 0
                    report["covers"] += 1 if obj.pop("_cover_written", False) else 0
            except KeyError as missing:
                raise BundleError(n, f"obligatoriskt fält {missing.args[0]!r} "
                                     "saknas — raden kan inte skrivas") from missing
            except OSError as refused:
                # F-B2: the cover write itself failed mid-file — a refusal
                # the parse phase cannot see, answered like every other.
                raise BundleError(n, f"omslaget kunde inte skrivas: "
                                     f"{refused}") from refused
            except sqlite3.Error as refused:
                # F-D2 leg 2 (MC 12451): the catch used to know only
                # IntegrityError — a bind this file's vocabulary cannot
                # see (InterfaceError and the rest of the family) escaped
                # as a 500. THE family belongs to this path, not one
                # subclass at a time.
                raise BundleError(n, f"raden duger inte för databasen: "
                                     f"{refused}") from refused
            if conflict:
                report["conflicts"].append({"book_key": obj["book_key"],
                                             "reason": "duplicate isbn"})
        conn.commit()
    except BundleError:
        conn.rollback()
        for rel in new_covers:               # written-but-rejected bytes
            (state_dir / rel).unlink(missing_ok=True)
        raise
    report["books"] = conn.execute("SELECT COUNT(*) FROM book").fetchone()[0]
    return {k: report[k] for k in
            ("books", "covers", "inserted", "updated", "conflicts")}


def init_bundle(app):

    @app.post("/seed")
    def seed_door():
        """The md import over HTTP (F-1): THE core, the CLI's own CSVs, the
        CLI's own counts line. Flagged rows answer 400 naming them — the
        import_seed exit-2 posture, never a silent shrug. P3-4 (MC 12451)
        adds the named refusals that used to 500: oversized body (413, the
        /bundle byte-budget idiom), broken utf-8 (400 "otillräcklig
        kodning"), unknown ## section (400 naming it) — all BEFORE a row is
        stored, so each 4xx leaves the DB untouched. F-C2 (MC 12451) makes
        the flagged path ATOMIC: nothing commits if any row is flagged.
        F-E2 (MC 12451): no Content-Length, no read — a body the transport
        never delimited would compare against zero caps and 200 about
        bytes the app never saw; the door answers 411 Length Required."""
        if request.headers.get("Content-Length") is None:
            return LENGTH_REQUIRED, 411
        body = request.get_data()
        if len(body) > MAX_SEED_BODY:
            return (f"Seed-filen är {len(body)} byte — budgetet är "
                    f"{MAX_SEED_BODY} byte (1 MiB) per anrop, samma budget "
                    "som för /bundle (§5.11/P1-1); dela upp den"), 413
        try:
            body.decode("utf-8")
        except UnicodeDecodeError:
            return ("Seed-filen kunde inte läsas som text: otillräcklig "
                    "kodning — skicka den som giltig UTF-8. Ingen rad är "
                    "importerad"), 400
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td) / "seed.md"
            raw.write_bytes(body)
            conn = db.get_db()
            try:
                # F-C2 (MC 12451): the commit is the DOOR's, not the core's.
                # Every 4xx from this route says "Ingen rad är importerad",
                # so the body lands as ONE transaction: a flagged or refused
                # row rolls the WHOLE import back, not just its own line.
                # (The CLI keeps its survivor posture — seed.load default.)
                report = seed.load(conn, raw, SEED_ALIASES, SEED_OVERRIDES,
                                   commit=False)
            except ValueError as fel:
                conn.rollback()
                return (f"Seed-filen duger inte: {fel}. Ingen rad är "
                        "importerad"), 400
        if report["flagged"]:
            conn.rollback()
            return ("Importeraden hittade rader den inte litar på: "
                    + ", ".join(report["flagged"])
                    + " — se data-import/import_overrides.csv. Ingen rad är "
                    "importerad"), 400
        conn.commit()
        return (f"parsed={report['parsed']} stored={report['stored']} "
                f"duplicates={report['duplicates']}")

    @app.post("/bundle")
    def bundle_door():
        # F-E2 (MC 12451): same posture as /seed — an undelimited body is
        # refused, never read as empty and answered 200.
        if request.headers.get("Content-Length") is None:
            return LENGTH_REQUIRED, 411
        raw = request.get_data()
        if len(raw) > MAX_BUNDLE_CHUNK:
            return (f"Bundle-delen är {len(raw)} byte — budgetet är "
                    f"{MAX_BUNDLE_CHUNK} byte per del (§5.11/P1-1); dela "
                    "upp den"), 400
        conn = db.get_db()
        try:
            lines = parse_bundle(raw)
            result = upsert_bundle(conn, db.state_base(), lines)
        except BundleError as e:
            # ONE path for both refusal kinds (P3-4, MC 12451): parse threw
            # before any write, or the upsert loop threw mid-file — the
            # single transaction unwinds every earlier line either way.
            conn.rollback()
            return (f"Bundle-filen är trasig på rad {e.line}: {e.reason} —"
                    " ingen rad är importerad"), 400
        return jsonify(result)
