"""S12 cover pass (scripts/cover_pass.py) — offline, transport faked, zero
network. The gates are the deliverable, so they are the subject: the page gate
and the Lane-E transcription gate must go RED on the two failure modes that
the 2026-11-13 calibration probes showed are real (an author PORTRAIT whose
og:image slug names the book, and a site LOGO served as og:image), and GREEN
on the verified true cover. store_cover discipline (manual-url, file+row in
step) is asserted on the one path that writes."""
import io

import pytest
from PIL import Image

from app import db, enrich
from scripts import cover_pass as cp


@pytest.fixture()
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    conn = db.connect()
    db.init_db(conn)
    conn.execute("INSERT INTO book (id, title, book_key, format, read_year,"
                 " status, isbn13, created, updated) VALUES (1,"
                 "'Där vildblommorna växer','vild','bok',2024,'read',"
                 "'9789180067171','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')")
    conn.commit()
    yield conn
    conn.close()


def img_bytes(w=700, h=1000):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "seagreen").save(buf, "JPEG", quality=90)
    return buf.getvalue()


BOOK = {"id": 1, "title": "Där vildblommorna växer", "author": "Louise Strömberg",
        "isbn13": "9789180067171", "isbn10": None, "status": "read"}

# ---- the shared normalization form -------------------------------------------

def test_normalize_is_slug_safe_for_swedish():
    assert cp.normalize("Där Vildblommorna Växer!") == cp.normalize("dar-vildblommorna-vaxer")


def test_stopwords_never_solely_decide_a_title():
    assert cp.sig_tokens("Ett liv") == ["liv"]
    assert cp.sig_tokens("Bland tåg och tanter") == ["bland", "tag", "tanter"]


# ---- the page gate ------------------------------------------------------------

PAGE_GOOD = ("<html><head><title>Där vildblommorna växer - Louise Strömberg"
             " | Bazar</title></head><body>x</body></html>")

def test_page_gate_accepts_title_and_author_in_heading():
    ok, why = cp.page_relevant(PAGE_GOOD, BOOK["title"], BOOK["author"], [])
    assert ok, why


def test_page_gate_refuses_a_page_without_the_book():
    ok, _ = cp.page_relevant("<title>Andra boken | Pusselbloggen</title>",
                             BOOK["title"], BOOK["author"], [])
    assert not ok


def test_page_gate_accepts_the_books_own_isbn_despite_hyphenation():
    page = "<p>ISBN 978-91-8006-717-1 — vildblommorna</p>"
    ok, why = cp.page_relevant(page, "Vilda blommor", "", ["9789180067171"])
    assert ok and "isbn" in why


def test_page_gate_reads_og_title_in_either_attribute_order():
    ok, _ = cp.page_relevant(
        '<meta property="og:title" content="Vilda blommor av Karin Sand">',
        "Vilda blommor", "Karin Sand", [])
    assert ok
    ok, _ = cp.page_relevant(
        '<meta content="Vilda blommor | Karin Sand" property="og:title">',
        "Vilda blommor", "Karin Sand", [])
    assert ok


# ---- the image gate (the calibration probes, encoded as expectations) -------

DESC_TRUE = ("Author name: LOUISE STRÖMBERG. Book title below: DÄR VILDBLOMMORNA "
             "VÄXER. Publisher word bottom left: BAZAR. The image shows a bokomslag.")

def test_image_gate_accepts_the_verified_true_cover():
    ok, why = cp.cover_confirms(DESC_TRUE, BOOK["title"], BOOK["author"])
    assert ok, why


def test_image_gate_refuses_an_author_portrait_with_no_printed_book():
    ok, _ = cp.cover_confirms(
        "En kvinna sitter i en soffa. Ingen text är tryckt på bilden.",
        BOOK["title"], BOOK["author"])
    assert not ok


def test_image_gate_refuses_the_wrong_book_even_by_the_same_author():
    ok, _ = cp.cover_confirms(
        "LOUISE STRÖMBERG — HELINAS RESA", BOOK["title"], BOOK["author"])
    assert not ok


def test_image_gate_refuses_when_only_the_author_is_printed():
    ok, _ = cp.cover_confirms("BAZAR förlag, LOUISE STRÖMBERG",
                              BOOK["title"], BOOK["author"])
    assert not ok


# ---- ranking -----------------------------------------------------------------

def test_isbn_in_url_outranks_everything_and_walls_never_appear():
    hits = [{"url": "https://blogg.example/x", "title": "Där vildblommorna växer"},
            {"url": "https://adlibris.com/b/9789180067171", "title": "…"},
            {"url": "https://witaj.example/doc.pdf", "title": "…"}]
    got = cp.rank_candidates(hits, BOOK["title"], ["9789180067171"],
                             blocked={"adlibris.com"})
    assert got == ["https://blogg.example/x"]      # isbn host blocked, pdf dropped


# ---- the per-book driver: one GREEN store, two honest RED paths --------------

class FakeFetch:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def __call__(self, url, **kw):
        self.calls.append(url)
        body = self.pages[url]
        if isinstance(body, Exception):
            raise body
        return body


def fake_search(hits):
    return lambda q: hits


def test_attempt_stores_only_after_both_gates_and_writes_manual_url(state):
    page = ('<html><head><title>Där vildblommorna växer - Louise Strömberg</title>'
            '<meta property="og:image" content="/bok.jpg"></head></html>')
    fetch = FakeFetch({"https://forlag.example/bok": page.encode(),
                       "https://forlag.example/bok.jpg": img_bytes()})
    row = cp.attempt_book(state, BOOK,
                          searcher=fake_search([{"url": "https://forlag.example/bok",
                                                 "title": "Där vildblommorna växer"}]),
                          fetch=fetch, describer=lambda b: DESC_TRUE)
    assert row["outcome"] == "covered" and row["cover_source"] == "manual-url"
    stored = state.execute("SELECT cover_path, cover_source FROM book WHERE id=1").fetchone()
    assert stored[1] == "manual-url" and stored[0] == "covers/1.jpg"
    assert (db.state_base() / "covers" / "1.jpg").exists()


def test_attempt_refuses_a_portrait_og_image_and_stores_nothing(state, tmp_path):
    page = ('<html><head><title>Där vildblommorna växer - Louise Strömberg</title>'
            '<meta property="og:image" content="/portrait.jpg"></head></html>')
    fetch = FakeFetch({"https://forfattare.example/bok": page.encode(),
                       "https://forfattare.example/portrait.jpg": img_bytes(1200, 800)})
    row = cp.attempt_book(state, BOOK,
                          searcher=fake_search([{"url": "https://forfattare.example/bok",
                                                 "title": "Där vildblommorna växer"}]),
                          fetch=fetch,
                          describer=lambda b: "En kvinna i soffa, ingen tryckt text.")
    assert row["outcome"] == "unresolved"
    assert state.execute("SELECT cover_path FROM book WHERE id=1").fetchone()[0] is None
    assert not (tmp_path / "covers" / "1.jpg").exists()


def test_search_engine_error_is_not_reported_as_no_hits(state):
    calls = []

    def flaky(q):
        calls.append(q)
        raise TimeoutError("engine timeout")

    row = cp.attempt_book(state, BOOK,
                          searcher=lambda q: cp.search(q, post=flaky),
                          fetch=FakeFetch({}), describer=lambda b: DESC_TRUE)
    assert row["outcome"] == "unresolved" and "sokfel" in row["detail"]
    assert len(calls) == 2                      # exactly one retry, then honest


def test_raw_swedish_url_is_encoded_before_fetch():
    got = cp.rank_candidates(
        [{"url": "https://bokborsen.example/view/Ahlström-Kristina/Hanna",
          "title": "Hanna i Provence"}], "Hanna i Provence", [], set())
    assert got == ["https://bokborsen.example/view/Ahlstr%C3%B6m-Kristina/Hanna"]


def test_dark_vision_stores_nothing_and_reports_loudly(state):
    page = ('<html><head><title>Där vildblommorna växer - Louise Strömberg</title>'
            '<meta property="og:image" content="/bok.jpg"></head></html>')
    fetch = FakeFetch({"https://forlag.example/bok": page.encode(),
                       "https://forlag.example/bok.jpg": img_bytes()})
    row = cp.attempt_book(state, BOOK,
                          searcher=fake_search([{"url": "https://forlag.example/bok",
                                                 "title": "Där vildblommorna växer"}]),
                          fetch=fetch, describer=lambda b: None)
    assert row["outcome"] == "unresolved" and "vision morkt" in row["detail"]
    assert state.execute("SELECT cover_path FROM book WHERE id=1").fetchone()[0] is None


def test_a_429_host_is_blocked_and_never_retried_within_the_pass(state):
    hits = [{"url": "https://adlibris.com/b/1", "title": "Där vildblommorna växer"},
            {"url": "https://adlibris.com/b/2", "title": "Där vildblommorna växer"}]
    fetch = FakeFetch({"https://adlibris.com/b/1": enrich.RateLimited("429")})
    blocked = set()
    row = cp.attempt_book(state, BOOK, searcher=fake_search(hits), fetch=fetch,
                          describer=lambda b: DESC_TRUE, blocked=blocked)
    assert row["outcome"] == "unresolved" and blocked == {"adlibris.com"}
    assert fetch.calls == ["https://adlibris.com/b/1"]   # b/2 never fetched


def test_downscale_keeps_a_valid_image_under_the_budget():
    small = cp.downscale_for_vision(img_bytes(3000, 4000))
    assert len(small) < enrich.MAX_FETCH
    assert Image.open(io.BytesIO(small)).size == (960, 1280)


# ---- the next-batch selector (S12b wave continuation) ------------------------

def test_prior_wave_ids_collects_ids_from_each_report(tmp_path):
    a, b = tmp_path / "w1.csv", tmp_path / "w2.csv"
    head = ",".join(cp.REPORT_FIELDS) + "\n"
    a.write_text(head + "7,x,,,,,,\n9,x,,,,,,\n")
    b.write_text(head + "9,x,,,,,,\n11,x,,,,,,\n")
    assert cp.prior_wave_ids([str(a), str(b)]) == {7, 9, 11}


def test_prior_wave_ids_refuses_a_malformed_report(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text(",".join(cp.REPORT_FIELDS) + "\nx,x,,,,,,\n")
    with pytest.raises(ValueError):        # never skip on a guessed id
        cp.prior_wave_ids([str(bad)])
