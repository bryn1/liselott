"""T5.3 — add a book, enrich it in-request, and close the cover loop honestly.

The plan's legs: POST title+author → 302 to the OWN /bok/<id>, the row lands
status read with today's date; the ISBN field runs the §7 normalizer; the new
row's book_key is the real §5.3 key (alias-resolved authors — the same
set_authors door as edit); POST /omslag/<id> runs the SAME single-book
enrichment the backfill loop uses (fixture transports here, live_transports in
production — no bundle, no VM350 in this path), with the 6 s budget and the
placeholder when every provider fails; multipart /omslag/<id>/ladda-up stores
cover_source='manual'.

Server-side bounds (P1-1: the nginx lane body cap is ≈1 MiB and no app may
reach it): a 950 000-byte file answers 400 with the plan's Swedish copy in
`.fel-meddelande`; a non-image answers 400; and the 1×1 stub gate lives in
store_cover — THE one normalizer, proven here through the upload door too.

Client-side guard (OQ-2 ruling b): omslag-upp.js downscales on a canvas to
≤680×1020 and re-encodes through the JPEG quality ladder [0.85, 0.75, 0.6]
while the blob exceeds 900000 bytes, and REFUSES the POST (inline Swedish
error) if the result is still over. The delivered bytes are what the browser
runs, so the test greps the delivered file — served through the app, not read
off disk."""
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from app import create_app, seed
from tests.test_browse import PASSWORD, seed_shelf

ROOT = Path(__file__).resolve().parent
COVER_FIXTURE = ROOT / "fixtures" / "cover_sample.jpg"


@pytest.fixture()
def shelf(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    app = create_app()
    app.testing = True
    client = app.test_client()
    assert client.post("/liselott/satt-loesenord",
                       data={"loesenord": PASSWORD, "bekrafta": PASSWORD}).status_code == 302
    return tmp_path, client


def token(client):
    with client.session_transaction("/liselott/logga-in") as sess:
        return sess["csrf"]


def row(db_path, cols, book_id):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(f"SELECT {', '.join(cols)} FROM book WHERE id = ?",
                            (book_id,)).fetchone()
    finally:
        conn.close()


def newest_id(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT MAX(id) FROM book").fetchone()[0]
    finally:
        conn.close()


def fixture_transports():
    """ol answers a policy-passing hit for WHATEVER title is asked (same
    shape tests/test_backfill_offline uses — the real match policy stays live);
    libris answers nothing; gb is not consulted (cooldown posture)."""

    def libris(title, authors):
        return []

    def ol(title, authors):
        return [{"source": "openlibrary", "title": title,
                 "authors": list(authors) or ["Någon"],
                 "isbn13": "9789198559699", "isbn10": None, "year": 2022,
                 "cover_id": 77,
                 "cover_url": "https://covers.openlibrary.org/b/id/77-M.jpg",
                 "subjects": ["Crime, Detective stories"]}]

    return {"libris": libris, "ol": ol, "gb": None}


def no_providers():
    """Every provider was asked and failed — the honest placeholder case."""
    from app.enrich_http import ProviderUnavailable

    def dead(title, authors):
        raise ProviderUnavailable("offline in test")

    return {"libris": dead, "ol": dead, "gb": dead}


def silent_providers(monkeypatch, transports=None):
    """Point the door's ONE seam at fixtures and drop the courtesy pacing —
    the suite never paces, production does (same call path as the CLI)."""
    from app import tillagg
    monkeypatch.setattr(tillagg, "live_transports",
                        lambda conn: transports or fixture_transports())
    monkeypatch.setattr(tillagg, "pacer", lambda seconds: None)
    monkeypatch.setattr(tillagg, "http_get",
                        lambda url, **kw: COVER_FIXTURE.read_bytes())


# ── the add page + POST ──────────────────────────────────────────────────────
def test_add_page_prefills_today_and_opens_the_shelf(shelf):
    page = shelf[1].get("/liselott/lagg-till")
    assert page.status_code == 200
    assert f'value="{date.today().isoformat()}"' in page.text   # today, not blank
    assert 'name="csrf"' in page.text


def test_post_lands_read_with_todays_date_and_a_real_key(shelf, monkeypatch):
    """The plan's first leg: 302 to the new book's OWN /bok/<id>, status read,
    date today, and the row's book_key is the real §5.3 key over canonical
    authors — not a placeholder."""
    tmp, client = shelf
    silent_providers(monkeypatch, no_providers())
    r = client.post("/liselott/lagg-till",
                    data={"titel": "Nästa bok", "forfattare": "Liselott Sjögren",
                          "csrf": token(client)})
    new_id = newest_id(tmp / "liselott.db")
    assert r.status_code == 302
    assert r.headers["Location"] == f"/liselott/bok/{new_id}"
    status, date_read, year, key = row(tmp / "liselott.db",
                                       ["status", "date_read", "read_year",
                                        "book_key"], new_id)
    assert status == "read"
    assert date_read == date.today().isoformat()
    assert year == date.today().year
    assert key == seed.book_key("Nästa bok", ["Liselott Sjögren"])


def test_isbn_field_is_stored_normalized(shelf, monkeypatch):
    tmp, client = shelf
    silent_providers(monkeypatch, no_providers())
    client.post("/liselott/lagg-till",
                data={"titel": "Med ISBN", "forfattare": "Någon",
                      "isbn13": "978-91-98559-69-9",
                      "csrf": token(client)})
    assert row(tmp / "liselott.db", ["isbn13"], newest_id(tmp / "liselott.db")) \
        == ("9789198559699",)


def test_bad_isbn_on_add_is_400_says_so_in_swedish(shelf, monkeypatch):
    tmp, client = shelf
    silent_providers(monkeypatch, no_providers())
    r = client.post("/liselott/lagg-till",
                    data={"titel": "Fel ISBN", "forfattare": "Någon",
                          "isbn13": "123", "csrf": token(client)})
    assert r.status_code == 400
    assert "fel-meddelande" in r.text and "ISBN" in r.text


def test_empty_title_on_add_is_400(shelf, monkeypatch):
    tmp, client = shelf
    r = client.post("/liselott/lagg-till",
                    data={"titel": "  ", "forfattare": "Någon",
                          "csrf": token(client)})
    assert r.status_code == 400


def test_adding_an_existing_title_and_author_is_400_not_a_duplicate(shelf, monkeypatch):
    """book_key UNIQUE IS the duplicate answer, and the real door is "adds the
    same book twice" (the fixture rows carry SYNTHETIC literal keys, so only a
    second real add can collide with the first row's real §5.3 key). The honest
    surface is a Swedish 400 — never a 500 and never a second row."""
    tmp, client = shelf
    silent_providers(monkeypatch, no_providers())
    data = {"titel": "Dubbel roman", "forfattare": "Dubbel Författare",
            "csrf": token(client)}
    assert client.post("/liselott/lagg-till", data=data).status_code == 302
    r = client.post("/liselott/lagg-till", data=data)
    assert r.status_code == 400
    assert "fel-meddelande" in r.text
    conn = sqlite3.connect(tmp / "liselott.db")
    assert conn.execute("SELECT COUNT(*) FROM book WHERE title = 'Dubbel roman'"
                        ).fetchone()[0] == 1
    conn.close()


# ── in-request enrichment on the production code path ────────────────────────
def test_an_added_book_enriches_itself_no_bundle_no_vm350(shelf, monkeypatch):
    """THE leg: add (ol fixture answers) → the row gains isbn/cover through the
    app's OWN resolve_book — the same function the backfill loop runs."""
    tmp, client = shelf
    silent_providers(monkeypatch)
    client.post("/liselott/lagg-till",
                data={"titel": "Stöld", "forfattare": "Ann-Helén Laestadius",
                      "isbn13": "9789198559699",   # matches the fixture row
                      "csrf": token(client)})
    new_id = newest_id(tmp / "liselott.db")
    isbn13, year, cover_path, source = row(
        tmp / "liselott.db", ["isbn13", "year", "cover_path", "cover_source"],
        new_id)
    assert isbn13 == "9789198559699" and year == 2022
    assert cover_path == f"covers/{new_id}.jpg" and source == "openlibrary"
    assert (tmp / "covers" / f"{new_id}.jpg").is_file()


def test_enrichment_failure_never_fails_the_add(shelf, monkeypatch):
    tmp, client = shelf
    silent_providers(monkeypatch, no_providers())
    r = client.post("/liselott/lagg-till",
                    data={"titel": "Utom räckhåll", "forfattare": "Någon",
                          "csrf": token(client)})
    assert r.status_code == 302
    new_id = newest_id(tmp / "liselott.db")
    cover, fail, tried = row(tmp / "liselott.db",
                             ["cover_path", "enrich_fail", "tried_providers"],
                             new_id)
    assert cover is None and fail == 1     # honest residue, placeholder painted
    assert "libris" in tried and "ol" in tried


# ── POST /omslag/<id>: the single-book "Hämta omslag" button ─────────────────
def test_hamta_omslag_button_fills_cover_and_source(shelf, monkeypatch):
    tmp, client = shelf
    silent_providers(monkeypatch)
    r = client.post("/liselott/omslag/1", data={"csrf": token(client)})
    assert r.status_code == 302
    assert r.headers["Location"] == "/liselott/redigera/1"
    cover, source = row(tmp / "liselott.db", ["cover_path", "cover_source"], 1)
    assert cover == "covers/1.jpg" and source == "openlibrary"
    assert (tmp / "covers" / "1.jpg").is_file()


def test_hamta_omslag_placeholder_when_all_providers_fail(shelf, monkeypatch):
    tmp, client = shelf
    silent_providers(monkeypatch, no_providers())
    r = client.post("/liselott/omslag/3", data={"csrf": token(client)})
    assert r.status_code == 302                      # no error page: the placeholder IS the answer
    assert row(tmp / "liselott.db", ["cover_path"], 3)[0] is None
    page = client.get("/liselott/cover/3")           # ...served honestly, no fake cover
    assert page.headers["Content-Type"].startswith("image/svg")


def test_hamta_omslag_never_paints_over_an_admins_own_cover(shelf, monkeypatch):
    """The M3 owner ruling (2d6b547) extends through the new door."""
    tmp, client = shelf
    conn = sqlite3.connect(tmp / "liselott.db")
    conn.execute("UPDATE book SET cover_source = 'manual-url', cover_path"
                 " = 'covers/1.jpg' WHERE id = 1")
    conn.commit()
    conn.close()
    silent_providers(monkeypatch)
    client.post("/liselott/omslag/1", data={"csrf": token(client)})
    assert row(tmp / "liselott.db", ["cover_source"], 1) == ("manual-url",)


def test_6s_budget_stops_asking_without_faking_attempts():
    """The budget is honest: providers it never asked are NOT recorded (they
    answer None = not consulted, the same posture as a cooldown), and nobody
    is asked past the deadline."""
    from app import enrich_loop
    clock = {"t": 0.0}
    asked = []

    def transport(title, authors):
        asked.append(title)
        return []

    def sleep(s):
        clock["t"] += s                       # pacing consumes the budget

    wrapped = enrich_loop.with_budget({"libris": transport, "ol": transport,
                                       "gb": None}, budget_s=6.0,
                                       sleep=sleep, clock=lambda: clock["t"])
    assert wrapped["libris"]("a", []) == []          # asked at t=1
    assert wrapped["ol"]("b", []) == []              # asked at t=2
    clock["t"] = 5.6                                 # one more pause crosses 6 s
    assert wrapped["libris"]("c", []) is None        # NOT asked — None, not an error
    assert asked == ["a", "b"]


# ── upload: the server-side caps (P1-1) ──────────────────────────────────────
def upload(client, book_id, data):
    return client.post(f"/liselott/omslag/{book_id}/ladda-up",
                       data=data, content_type="multipart/form-data")


def test_upload_stores_cover_source_manual(shelf):
    tmp, client = shelf
    from io import BytesIO
    r = upload(client, 3, {"csrf": token(client), "fil": (BytesIO(COVER_FIXTURE.read_bytes()),
                                                          "omslag.jpg")})
    assert r.status_code == 302
    assert row(tmp / "liselott.db", ["cover_source"], 3) == ("manual",)
    assert (tmp / "covers" / "3.jpg").is_file()


def test_upload_950k_body_is_400_with_the_plans_swedish_copy(shelf):
    """950 000 B passes the 1 MiB edge and must die HERE, naming the fix — the
    client-side downscale exists so she rarely sees this, but the server is the
    one that holds the line (P1-1)."""
    tmp, client = shelf
    from io import BytesIO
    r = upload(client, 3, {"csrf": token(client),
                           "fil": (BytesIO(b"\xff\xd8\xff" + b"x" * 949_997),
                                   "stor.jpg")})
    assert r.status_code == 400
    assert "fel-meddelande" in r.text
    assert "Bilden är för stor — ladda upp en mindre fil" in r.text
    assert row(tmp / "liselott.db", ["cover_path"], 3)[0] is None


def test_upload_non_image_is_400(shelf):
    tmp, client = shelf
    from io import BytesIO
    r = upload(client, 3, {"csrf": token(client),
                           "fil": (BytesIO("det här är ingen bild".encode()),
                                   "lagtext.txt")})
    assert r.status_code == 400
    assert "fel-meddelande" in r.text
    assert not (tmp / "covers" / "3.jpg").exists()


def test_upload_1x1_stub_gate_is_rejected(shelf):
    """THE one normalizer guards this door too (d7fd436): a 1×1 GIF is not a
    cover — no fake covers, ever."""
    tmp, client = shelf
    from io import BytesIO
    stub = (ROOT / "fixtures" / "ol_no_cover_stub.gif").read_bytes()
    r = upload(client, 3, {"csrf": token(client), "fil": (BytesIO(stub), "stub.gif")})
    assert r.status_code == 400
    assert "fel-meddelande" in r.text
    assert not (tmp / "covers" / "3.jpg").exists()


def test_upload_without_a_file_is_400(shelf):
    client = shelf[1]
    r = upload(client, 3, {"csrf": token(client)})
    assert r.status_code == 400


# ── the client-side downscale guard: grepped IN THE DELIVERED FILE ────────────
def test_edit_page_ships_the_guard_with_constants_and_ladder(shelf):
    """Asserted against the DECLARATION lines, not prose: a plain substring
    grep matched the constants quoted in the file's header COMMENT and stayed
    green with the real ladder broken (measured — the first version of this
    test did exactly that; the planted-red run below only goes RED because
    the assertions now parse the declarations)."""
    import re

    page = shelf[1].get("/liselott/redigera/3")
    assert "/liselott/static/js/omslag-upp.js" in page.text   # served via url_for
    js = shelf[1].get("/liselott/static/js/omslag-upp.js")
    assert js.status_code == 200
    body = js.get_data(as_text=True)
    assert re.search(r"OMSLAG_MAX_W\s*=\s*680\s*;", body)          # ≤680…
    assert re.search(r"OMSLAG_MAX_H\s*=\s*1020\s*;", body)         # …×1020 canvas
    assert re.search(r"OMSLAG_MAX_BYTES\s*=\s*900000\s*;", body)   # the ONE budget
    ladder = re.search(r"OMSLAG_QUALITY_LADDER\s*=\s*\[([0-9.,\s]+)\]", body)
    assert ladder is not None
    steps = [float(x) for x in ladder.group(1).split(",")]
    assert steps == [0.85, 0.75, 0.6]                        # the full ladder
    assert "uppladdningsfel" in body                         # refusal target node
    assert "preventDefault" in body                          # refuses to POST over cap
