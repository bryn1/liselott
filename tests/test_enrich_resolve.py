"""T3.4 — provider ORDER libris→ol→gb + the match policy (difflib similarity
≥ 0.80 on normalized titles, author gate when both sides carry authors) +
store_cover (THE one cover normalizer — upload T5.3 and bundle write T6.4
reuse it, no second pipeline) + tried_providers/enrich_fail (the F-2 evidence
columns T5.5's `unobtainable` list reads) + `/cover/<id>` answering the
placeholder SVG for a coverless row.

Transports and the cover fetcher are parameters, so this file never touches
the network: the OL fixture, the SYNTHETIC Libris fixtures and a SYNTHETIC
generated JPEG (tests/fixtures/cover_sample.jpg — 600×900, so the ≤340×510
downscale is actually exercised) drive every leg."""
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from app import create_app, db, enrich, enrich_ol

ROOT = Path(__file__).resolve().parent.parent
OL_FIXTURE = ROOT / "tests" / "fixtures" / "ol_stold.json"
LIBRIS_FIND = ROOT / "tests" / "fixtures" / "libris_find.json"
COVER_FIXTURE = ROOT / "tests" / "fixtures" / "cover_sample.jpg"

STOLD = dict(title="Stöld", authors=["Ann-Helén Laestadius"])


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    c = db.connect()
    db.init_db(c)
    insert_book(c)
    yield c
    c.close()


def insert_book(c, key="stold-1", **over):
    row = dict(title=STOLD["title"], book_key=key, format="bok", read_year=2022,
               status="read", created="2026-01-01T00:00:00Z",
               updated="2026-01-01T00:00:00Z")
    row.update(over)
    cols, marks = ", ".join(row), ", ".join("?" for _ in row)
    cur = c.execute(f"INSERT INTO book ({cols}) VALUES ({marks})", tuple(row.values()))
    if over.get("authors") is not None:
        for name in row.pop("authors", None) or STOLD["authors"]:
            aid = c.execute("INSERT INTO author (name) VALUES (?) "
                            "ON CONFLICT(name) DO UPDATE SET name=name",
                            (name,)).lastrowid
            c.execute("INSERT OR IGNORE INTO book_author (book_id, author_id) "
                      "VALUES (?, ?)", (cur.lastrowid, aid))
    else:
        aid = c.execute("INSERT INTO author (name) VALUES (?)",
                        (STOLD["authors"][0],)).lastrowid
        c.execute("INSERT INTO book_author (book_id, author_id) VALUES (?, ?)",
                  (cur.lastrowid, aid))
    c.commit()
    return cur.lastrowid


def book_row(c, book_id):
    c.row_factory = None
    cols = ("id", "title", "isbn13", "isbn10", "year", "cover_path",
            "cover_source", "tried_providers", "enrich_fail")
    row = c.execute(f"SELECT {', '.join(cols)} FROM book WHERE id = ?",
                    (book_id,)).fetchone()
    return dict(zip(cols, row))


def genres_of(c, book_id):
    return [r[0] for r in c.execute(
        "SELECT g.name FROM genre g JOIN book_genre bg ON bg.genre_id = g.id "
        "WHERE bg.book_id = ? ORDER BY g.name", (book_id,))]


def ol_transport(payload):
    """OL transport over a recorded payload, mapped by the REAL client."""
    def transport(title, author, **kw):
        return enrich_ol.map_docs(json.loads(json.dumps(payload)))
    return transport


def libris_transport(docs):
    def transport(title, author, **kw):
        return docs
    return transport


def failing_transport(title, author, **kw):
    raise enrich.ProviderUnavailable("transport failed")


def ol_hit_transport():
    return ol_transport(json.loads(OL_FIXTURE.read_text(encoding="utf-8")))


def cover_fetch():
    data = COVER_FIXTURE.read_bytes()

    def fetch(url, **kw):
        assert url.startswith("https://covers.openlibrary.org/"), url
        return data
    return fetch


# ---- provider order + match policy -----------------------------------------

def test_stold_resolves_through_the_provider_order(conn):
    book_id = conn.execute("SELECT id FROM book").fetchone()[0]
    transports = {
        "libris": libris_transport([]),          # libris answers: nothing
        "ol": ol_hit_transport(),
        "gb": failing_transport,                 # must never be reached
    }
    outcome = enrich.resolve_book(conn, book_id, transports=transports,
                                  fetch=cover_fetch())
    assert outcome["source"] == "openlibrary"
    row = book_row(conn, book_id)
    assert row["isbn13"] == "9789198559699"
    assert row["isbn10"] == "9198559699"
    assert row["year"] == 2022
    assert row["cover_source"] == "openlibrary"
    assert row["cover_path"] == f"covers/{book_id}.jpg"
    assert row["tried_providers"] == "libris,ol"   # gb never consulted after a hit
    assert row["enrich_fail"] == 0
    assert genres_of(conn, book_id) == ["Övrigt"]  # §5: no subjects → Övrigt


def test_libris_wins_when_it_matches_first(conn):
    book_id = conn.execute("SELECT id FROM book").fetchone()[0]
    libris_hit = [{"source": "libris", "id": "librisdoc:b1", "title": "Stöld",
                   "authors": ["Ann-Helén Laestadius"], "isbn13": "9789198559699",
                   "isbn10": None, "year": 2022, "cover_id": None,
                   "cover_url": None, "subjects": ["Skönlitteratur", "Romaner"]}]
    seen = []
    outcome = enrich.resolve_book(
        conn, book_id,
        transports={"libris": libris_transport(libris_hit),
                    "ol": lambda *a, **k: seen.append("ol") or [],
                    "gb": failing_transport},
        fetch=cover_fetch())
    assert outcome["source"] == "libris"
    assert seen == []                            # order: later providers skipped
    assert genres_of(conn, book_id) == ["Övrigt"]  # Skönlitteratur/Romaner map nowhere
    row = book_row(conn, book_id)
    assert (row["cover_path"], row["cover_source"]) == (None, None)  # no cover_url


def test_similarity_below_0_80_does_not_match(conn):
    book_id = conn.execute("SELECT id FROM book").fetchone()[0]
    weak = [{"source": "openlibrary", "title": "Stöld och andra noveller om natten",
             "authors": ["Ann-Helén Laestadius"], "isbn13": "9780000000000",
             "isbn10": None, "year": 1999, "cover_id": None, "cover_url": None,
             "subjects": []}]
    outcome = enrich.resolve_book(
        conn, book_id,
        transports={"libris": libris_transport([]),
                    "ol": libris_transport(weak), "gb": libris_transport([])})
    assert outcome["resolved"] is False
    row = book_row(conn, book_id)
    assert (row["isbn13"], row["isbn10"], row["year"], row["cover_path"]) == \
        (None, None, None, None)                # payload untouched
    # the F-2 evidence columns DO record the verified attempt (§5/T5.5):
    assert row["tried_providers"] == "libris,ol,gb"
    assert row["enrich_fail"] == 1


def test_author_gate_blocks_a_title_only_match(conn):
    book_id = conn.execute("SELECT id FROM book").fetchone()[0]
    impostor = [{"source": "openlibrary", "title": "Stöld",
                 "authors": ["Kalle Anka"], "isbn13": "9781111111111",
                 "isbn10": None, "year": 1901, "cover_id": None,
                 "cover_url": None, "subjects": []}]
    outcome = enrich.resolve_book(
        conn, book_id,
        transports={"libris": libris_transport([]),
                    "ol": libris_transport(impostor), "gb": libris_transport([])})
    assert outcome["resolved"] is False
    assert conn.execute("SELECT isbn13 FROM book").fetchone()[0] is None


def test_author_gate_opens_when_the_book_has_no_author(conn):
    """§T3.4 gate reads "when BOTH sides have authors" — a diary row without an
    author is not blocked by a provider that names one."""
    book_id = insert_book_no_author(conn)
    hit = [{"source": "openlibrary", "title": "Ta min hand",
            "authors": ["Någon Författare"], "isbn13": "9782222222222",
            "isbn10": None, "year": 2019, "cover_id": None, "cover_url": None,
            "subjects": []}]
    outcome = enrich.resolve_book(
        conn, book_id,
        transports={"libris": libris_transport([]),
                    "ol": libris_transport(hit), "gb": libris_transport([])})
    assert outcome["resolved"] is True
    assert conn.execute("SELECT isbn13 FROM book WHERE id = ?",
                        (book_id,)).fetchone()[0] == "9782222222222"


def insert_book_no_author(conn):
    cur = conn.execute(
        "INSERT INTO book (title, book_key, format, read_year, status, created, updated)"
        " VALUES ('Ta min hand','no-author-1','bok',2019,'read',"
        "'2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')")
    conn.commit()
    return cur.lastrowid


def test_all_providers_failing_records_the_failure_and_never_crashes(conn):
    book_id = conn.execute("SELECT id FROM book").fetchone()[0]
    outcome = enrich.resolve_book(
        conn, book_id,
        transports={"libris": failing_transport, "ol": failing_transport,
                    "gb": failing_transport})
    assert outcome["resolved"] is False
    row = book_row(conn, book_id)
    assert row["enrich_fail"] == 1
    assert row["tried_providers"] == "libris,ol,gb"


def test_a_provider_in_cooldown_is_skipped_not_recorded(conn):
    """gb cooling down is not an attempt — the evidence column stays honest
    (T5.5's unobtainable reads "all 3 names")."""
    book_id = conn.execute("SELECT id FROM book").fetchone()[0]
    outcome = enrich.resolve_book(
        conn, book_id,
        transports={"libris": libris_transport([]), "ol": libris_transport([]),
                    "gb": None},                       # unavailable right now
        fetch=cover_fetch())
    assert outcome["resolved"] is False
    assert book_row(conn, book_id)["tried_providers"] == "libris,ol"


# ---- store_cover: THE normalizer -------------------------------------------

def test_store_cover_normalizes_to_jpeg_under_340x510(conn, tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    book_id = conn.execute("SELECT id FROM book").fetchone()[0]
    rel = enrich.store_cover(conn, book_id, COVER_FIXTURE.read_bytes(), "openlibrary")
    assert rel == f"covers/{book_id}.jpg"
    out = tmp_path / rel
    assert out.exists()
    with Image.open(out) as img:
        assert img.format == "JPEG"
        assert img.size[0] <= 340 and img.size[1] <= 510
        assert img.size == (340, 510)          # 600×900 downscale actually ran


def test_store_cover_refuses_non_image_bytes(conn, tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    with pytest.raises(enrich.CoverRejected):
        enrich.store_cover(conn, 1, b"<html>not a jpeg</html>", "openlibrary")
    assert not (tmp_path / "covers" / "1.jpg").exists()


def test_cover_fetch_over_budget_is_refused(conn):
    def huge(url, **kw):
        return b"x" * (enrich.MAX_BODY + 1)
    with pytest.raises(enrich.BodyTooLarge):
        enrich.fetch_cover("https://covers.openlibrary.org/b/id/1-M.jpg",
                           fetch=huge)


def test_fetch_cover_rejects_non_http_scheme():
    with pytest.raises(enrich.CoverRejected):
        enrich.fetch_cover("file:///etc/passwd", fetch=lambda url, **k: b"")


# ---- /cover/<id> -----------------------------------------------------------

PASSWORD = "_test_losenord_"


def authed_client(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    app = create_app()
    app.testing = True
    client = app.test_client()
    assert client.post("/liselott/satt-loesenord",
                       data={"loesenord": PASSWORD, "bekrafta": PASSWORD}).status_code == 302
    return app, client


def test_cover_route_serves_the_placeholder_for_a_coverless_row(tmp_path, monkeypatch):
    app, client = authed_client(tmp_path, monkeypatch)
    conn = db.connect()
    db.init_db(conn)
    book_id = insert_book(conn)
    conn.close()
    r = client.get(f"/liselott/cover/{book_id}")
    assert r.status_code == 200
    assert r.mimetype == "image/svg+xml"
    svg = (ROOT / "app" / "static" / "omslag-saknas.svg").read_bytes()
    assert r.data == svg                       # the placeholder file, not a stub
    assert b"Omslag saknas" in svg             # §9 copy lives in the svg


def test_cover_route_serves_the_stored_jpeg(tmp_path, monkeypatch):
    app, client = authed_client(tmp_path, monkeypatch)
    conn = db.connect()
    db.init_db(conn)
    book_id = insert_book(conn)
    enrich.store_cover(conn, book_id, COVER_FIXTURE.read_bytes(), "openlibrary")
    conn.close()
    r = client.get(f"/liselott/cover/{book_id}")
    assert r.status_code == 200
    assert r.mimetype == "image/jpeg"
    assert len(r.data) > 1000                  # real bytes, not the placeholder


def test_cover_route_unknown_id_is_404(tmp_path, monkeypatch):
    _, client = authed_client(tmp_path, monkeypatch)
    assert client.get("/liselott/cover/9999").status_code == 404


def test_cover_route_never_follows_a_path_outside_the_covers_dir(tmp_path, monkeypatch):
    """/cover builds a filesystem path from a DB column. Only store_cover writes
    that column (a fixed covers/<id>.jpg shape), but a route must not turn a
    corrupted or hand-edited value into an arbitrary file read — a traversal
    value serves the placeholder, never the file it points at."""
    app, client = authed_client(tmp_path, monkeypatch)
    conn = db.connect()
    db.init_db(conn)
    book_id = insert_book(conn)
    secret = tmp_path / "hemlighet.txt"
    secret.write_text("HEMLIG TEXT", encoding="utf-8")
    conn.execute("UPDATE book SET cover_path = ?, cover_source = 'manual' WHERE id = ?",
                 ("hemlighet.txt", book_id))
    conn.execute("UPDATE book SET cover_path = ?, cover_source = 'manual' WHERE id = ?",
                 ("../../../etc/passwd", book_id + 1))     # if a 2nd row exists
    conn.commit()
    conn.close()
    svg = (ROOT / "app" / "static" / "omslag-saknas.svg").read_bytes()
    r = client.get(f"/liselott/cover/{book_id}")
    assert r.status_code == 200 and r.data == svg, "the route served a non-cover file"


def test_an_admins_manual_url_cover_is_never_overwritten(conn):
    """'manual' was the only value the overwrite rule protected; 'manual-url'
    (the OQ-2 ruling) is just as much the admin's own choice — a backfill pass
    must not paint over it with whatever a provider offers."""
    book_id = conn.execute("SELECT id FROM book").fetchone()[0]
    enrich.store_cover(conn, book_id, COVER_FIXTURE.read_bytes(), "manual-url")
    before = conn.execute("SELECT cover_path, cover_source FROM book WHERE id = ?",
                          (book_id,)).fetchone()
    assert before[1] == "manual-url"
    enrich.resolve_book(
        conn, book_id,
        transports={"libris": libris_transport([]), "ol": ol_hit_transport(),
                    "gb": libris_transport([])},
        fetch=cover_fetch())
    assert conn.execute("SELECT cover_path, cover_source FROM book WHERE id = ?",
                        (book_id,)).fetchone() == before
