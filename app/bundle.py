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
anything (leg g).

Both doors sit in auth.TOKENLESS_POSTS (the §6.6 machine trio's vocabulary):
no CSRF token, but a foreign Origin still 400s (P2-r4) and no session still
302s — and there is NO seed token (F-7: the owner session IS the gate, in
every state; the plan retires the one-time door).
"""
import base64
import json
import tempfile
from pathlib import Path

from flask import jsonify, request

from app import REPO_ROOT, auth, db, enrich, seed

MAX_BUNDLE_CHUNK = 900_000          # §5.11 re-pinned by P1-1: refuse larger
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


def _store_new(conn, obj, now):
    """A book_key the DB never saw lands AS-IS (§5.11): status/read_year/
    date_read/rating/format exactly as exported — a wishline keeps its
    read_year 0 sentinel, a read row its date. The only refusal an INSERT
    can hit is the ISBN first-writer rule: then the row still lands, ISBN
    less, and this returns its conflict. Returns (conflict, cover_written)."""
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
        enrich.store_cover(conn, book_id, obj["_cover_bytes"],
                           obj.get("cover_source") or "openlibrary")
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
                               obj.get("cover_source") or "openlibrary")
            obj["_cover_written"] = True
            touched = True
    obj["_touched"] = touched
    return conflict


def upsert_bundle(conn, state_dir, lines) -> dict:
    """The §5.11 merge, ONE transaction per POST (rollback is the route's
    job on parse refusal — parsing already guarantees nothing wrote).
    Response keys the T6.4 DoD pins verbatim: books / covers / inserted /
    updated / conflicts."""
    report = {"covers": 0, "inserted": 0, "updated": 0, "conflicts": []}
    for obj in lines:
        row = conn.execute(
            "SELECT id, isbn13, isbn10, year, cover_path, cover_source"
            " FROM book WHERE book_key = ?", (obj["book_key"],)).fetchone()
        if row is None:
            conflict, written = _store_new(conn, obj, auth.utcnow_iso())
            report["inserted"] += 1
            report["covers"] += 1 if written else 0
        else:
            conflict = _merge_into(conn, state_dir, row, obj)
            report["updated"] += 1 if obj.pop("_touched", False) else 0
            report["covers"] += 1 if obj.pop("_cover_written", False) else 0
        if conflict:
            report["conflicts"].append({"book_key": obj["book_key"],
                                        "reason": "duplicate isbn"})
    conn.commit()
    report["books"] = conn.execute("SELECT COUNT(*) FROM book").fetchone()[0]
    return {k: report[k] for k in
            ("books", "covers", "inserted", "updated", "conflicts")}


def init_bundle(app):

    @app.post("/seed")
    def seed_door():
        """The md import over HTTP (F-1): THE core, the CLI's own CSVs, the
        CLI's own counts line. Flagged rows answer 400 naming them — the
        import_seed exit-2 posture, never a silent shrug."""
        body = request.get_data()
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td) / "seed.md"
            raw.write_bytes(body)
            conn = db.get_db()
            report = seed.load(conn, raw, SEED_ALIASES, SEED_OVERRIDES)
        if report["flagged"]:
            return ("Importeraden hittade rader den inte litar på: "
                    + ", ".join(report["flagged"])
                    + " — se data-import/import_overrides.csv"), 400
        return (f"parsed={report['parsed']} stored={report['stored']} "
                f"duplicates={report['duplicates']}")

    @app.post("/bundle")
    def bundle_door():
        raw = request.get_data()
        if len(raw) > MAX_BUNDLE_CHUNK:
            return (f"Bundle-delen är {len(raw)} byte — budgetet är "
                    f"{MAX_BUNDLE_CHUNK} byte per del (§5.11/P1-1); dela "
                    "upp den"), 400
        conn = db.get_db()
        try:
            lines = parse_bundle(raw)
        except BundleError as e:
            conn.rollback()          # belt: parse wrote nothing by design
            return (f"Bundle-filen är trasig på rad {e.line}: {e.reason} —"
                    " ingen rad är importerad"), 400
        return jsonify(upsert_bundle(conn, db.state_base(), lines))
