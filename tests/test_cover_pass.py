"""S12 cover pass (scripts/cover_pass.py) — offline, transport faked, zero
network. The gates are the deliverable, so they are the subject: the page gate
and the Lane-E transcription gate must go RED on the two failure modes that
the 2026-11-13 calibration probes showed are real (an author PORTRAIT whose
og:image slug names the book, and a site LOGO served as og:image), and GREEN
on the verified true cover. store_cover discipline (manual-url, file+row in
step) is asserted on the one path that writes."""
import io
import os

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
                 "'Där lingonrisen susar','vild','bok',2024,'read',"
                 "'9789173710176','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')")
    conn.commit()
    yield conn
    conn.close()


def img_bytes(w=700, h=1000):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "seagreen").save(buf, "JPEG", quality=90)
    return buf.getvalue()


BOOK = {"id": 1, "title": "Där lingonrisen susar", "author": "Lovisa Strand",
        "isbn13": "9789173710176", "isbn10": None, "status": "read"}

# ---- the shared normalization form -------------------------------------------

def test_normalize_is_slug_safe_for_swedish():
    assert cp.normalize("Där Vildblommorna Växer!") == cp.normalize("dar-vildblommorna-vaxer")


def test_stopwords_never_solely_decide_a_title():
    assert cp.sig_tokens("Ett liv") == ["liv"]
    assert cp.sig_tokens("Bland tåg och tanter") == ["bland", "tag", "tanter"]


# ---- the page gate ------------------------------------------------------------

PAGE_GOOD = ("<html><head><title>Där lingonrisen susar - Lovisa Strand"
             " | Bazar</title></head><body>x</body></html>")

def test_page_gate_accepts_title_and_author_in_heading():
    ok, why = cp.page_relevant(PAGE_GOOD, BOOK["title"], BOOK["author"], [])
    assert ok, why


def test_page_gate_refuses_a_page_without_the_book():
    ok, _ = cp.page_relevant("<title>Andra boken | Pusselbloggen</title>",
                             BOOK["title"], BOOK["author"], [])
    assert not ok


def test_page_gate_accepts_the_books_own_isbn_despite_hyphenation():
    page = "<p>ISBN 978-91-7371-017-6 — vildblommorna</p>"
    ok, why = cp.page_relevant(page, "Vilda blommor", "", ["9789173710176"])
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

DESC_TRUE = ("Author name: LOVISA STRAND. Book title below: DÄR LINGONRISEN "
             "SUSAR. Publisher word bottom left: FJÄLLNYAN. The image shows a bokomslag.")

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
        "LOVISA STRAND — KARIN I DALARNA", BOOK["title"], BOOK["author"])
    assert not ok


def test_image_gate_refuses_when_only_the_author_is_printed():
    ok, _ = cp.cover_confirms("FJÄLLNYAN förlag, LOVISA STRAND",
                              BOOK["title"], BOOK["author"])
    assert not ok


# ---- the artifact-tolerance class (MC 12649; the MC 12648 wave-15 law) ------
# Wave-1 rejected right-book covers whose transcription split the printed
# title across a line hyphen or a line break (own-isbn sample: 5/5 refused
# identically, correct author printed). The real wave-15 strings live in the
# Hemsidor audit OUT/.tmp/wave15/ and NEVER in this public repo (MC 12523
# exposure law: diary strings stay out of tracked files — fixtures here are
# synthetic in the DESC_TRUE/BOOK style, shaped on the wave evidence).
# Wave-15b rescued the class with a wave-side patch (OUT/.tmp/wave15/
# compare2.py); that patch's WHOLESALE whitespace-strip also opened a
# boundary face — DA-verdict-c14 executed 4 false-accept repros (a DIFFERENT
# book by the SAME author whose blurb/särskrivning prose glues a DB title
# token across printed word walls). The law that now lives in the gate is
# the DA-belted one: LINE SEAMS transparent (seam_space), spaces and
# punctuation word walls — the 9-row wave rescue survives exactly, the 4
# faces are shut. Author check stays strict, abstain class unchanged (MC
# 12648 ruling: the gate must not reject correct covers — nothing says it
# must accept wrong ones).

def test_image_gate_rescues_the_line_hyphenated_transcription():
    # Shaped on wave-15 rows 164/245 (hyphen + newline mid-word). Wave 1
    # refused that class "bara 0/1 titelord tryckta i bilden" — reproduced
    # verbatim on the pre-change gate with the REAL stored descs, MC 12649
    # evidence; compare2 passed them.
    ok, why = cp.cover_confirms(
        "ROMAN\nNatt-\nstickning\nAlbert\nFörlag\nELSA\nVIDE\n\nThe "
        "image shows a bokomslag (book cover) with a teal background.",
        "Nattstickning", "Elsa Vide")
    assert ok, why
    ok, why = cp.cover_confirms(
        "MÅNSKENS-\nSICKLINGEN\nÅRETS\nDECKAR-\nFÖRFATTARE\n2019\n"
        "ELSA VIDE\nUPPLÄSARE: VEM VEMLÖF\n\nThe image is a book "
        "(audiobook) cover.", "Månskenssicklingen", "Elsa Vide")
    assert ok, why


def test_image_gate_rescues_the_line_split_without_hyphen():
    # The same artifact's other half (wave-15 rows 12/14 shaped): the
    # transcription splits a printed word at a line break WITHOUT printing
    # the hyphen.
    ok, why = cp.cover_confirms(
        "ELSA VIDE\n\"Elsa Vide är den bästa nya rösten\nLUCINDA "
        "PENNELL\nTall\nMYRARNA\nHAMNPLAN\nFÖRLAGET\n\nBokomslag.",
        "Tallmyrarna", "Elsa Vide")
    assert ok, why
    ok, why = cp.cover_confirms(
        "FYR\nKVARNEN\nROMAN\nELSA\nVIDE\nHarperCollins\n\nThe image "
        "is a bokomslag (book cover).", "Fyrkvarnen", "")  # row-14 shape:
    assert ok, why                            # the DB carried no author field


def test_image_gate_still_refuses_the_wrong_author_under_the_tolerance():
    # Title fully printed, a DIFFERENT author printed: the rescue must not
    # leak a wrong-author apply — artifact tolerance is titles ONLY.
    ok, _ = cp.cover_confirms("DÄR LINGONRISEN SUSAR av KARIN SANDELL",
                              BOOK["title"], BOOK["author"])
    assert not ok
    # Sharper mutant-killer: the right author's surname appears ONLY once
    # whitespace is deleted ("STR ANDERSSON" compacts to "strand..."). An
    # implementation that compacted the AUTHOR side too would pass this row;
    # the strict token space must not.
    ok, _ = cp.cover_confirms(
        "DÄR LINGONRISEN SUSAR av FORFATTAREN STR ANDERSSON",
        BOOK["title"], BOOK["author"])
    assert not ok


def test_image_gate_still_abstains_without_distinctive_words():
    # Wave-15 row 684 (an initials-acronym title, synthetic shape here): the
    # title has no distinctive tokens, so the gate refuses to decide at all —
    # the abstain
    # class is UNCHANGED by the tolerance (compare2 passed that row on
    # author-only evidence; the repo law says abstain stands).
    ok, why = cp.cover_confirms(
        "Av författaren Elsa Vide\nP.m.\nVide & Co\n»En nyhet«\n"
        "Elle\n\nThe image is a book cover (bokomslag) featuring three",
        "P.M.", "Elsa Vide")
    assert (ok, why) == (False, "titeln har inga sarskiljande ord")


def test_image_gate_refuses_the_boundary_glue_fixtures():
    # DA-verdict-c14 F-DA14-1 (OUT/.tmp/da-c14/boundary.py, fixtures kept
    # verbatim): a DIFFERENT book by the SAME author whose cover prose glues
    # a distinctive DB-title token ONLY across printed word walls. All four
    # ran ACCEPT under the c1 whitespace-stripped retry (RED-first) and all
    # four are refused by the seam belt; the fifth face refused throughout.
    ok, _ = cp.cover_confirms(                       # blurb_period_glue_1token
        "ELSA VIDE\nRegn över skärgården\nROMAN\n\"Den bästa berättelsen "
        "om en sommar. Regnen och tystnaden.\"\nBazar\n\nBokomslag.",
        "Sommarregn", "Elsa Vide")
    assert not ok
    ok, _ = cp.cover_confirms(                       # two_word_wrong_title
        "ELSA VIDE\nSommar regn\nBERÄTTELSER FRÅN ÖLAND\nBazar\n\nBokomslag.",
        "Sommarregn", "Elsa Vide")
    assert not ok
    ok, _ = cp.cover_confirms(                       # sibling_title_glue_2token
        "Resor vid västkusten\nELSA VIDE\nFyr, kvarnen och Skagen\n"
        "REPORTAGE\nBokförlaget VidHAVET\n\nBokomslag.",
        "Fyrkvarnen på Skagen", "Elsa Vide")
    assert not ok
    ok, _ = cp.cover_confirms(                       # space_glue_nattoppet
        "ELSA VIDE\nMOTELLJUS\nROMAN\n\"Receptionen har natt öppet året "
        "om.\"\nWahlström\n\nBokomslag.", "Nattöppet", "Elsa Vide")
    assert not ok
    ok, _ = cp.cover_confirms(                       # blurb_karlek_romanen
        "ELSA VIDE\nKATTHISTORIER\n\"Det är en kärlek. Romanen om Maj är "
        "årets mest sålda.\"\nBokförlaget Noran\n\nBokomslag.",
        "Kärleksromanen", "Elsa Vide")
    assert not ok


# The wave-replay leg below pins the FIX-WAVE acceptance facts over the REAL
# stored wave-15 corpus (56 transcriptions). The corpus is personal data
# outside the public repo, so the leg runs where the audit dir exists (the
# fleet seat) and skips elsewhere — the skipif-guarded live-leg shape already
# used by tests/test_ai_rek_pass.py. OLD_PASS below is the pass-set of
# cover_confirms at 859457f (git-show-extracted pre-change gate, MC 12649
# fix-wave evidence); the fix-wave law must pass exactly OLD_PASS plus the
# nine line-split rows the wave-15 ruling rescued, no other row.
WAVE15_CORPUS = "/home/claudecode/Hemsidor/.audits/202611161817-aae834ce-n1/" \
                "out/.tmp/wave15/vision.jsonl"
WAVE15_OLD_PASS = frozenset({1, 8, 62, 91, 104, 119, 122, 125, 134, 143, 155,
                             177, 198, 247, 253, 282, 329, 330, 336, 344, 361,
                             382, 440, 446, 448, 486, 530, 555, 600, 633, 655,
                             656, 669, 670, 689, 720, 722})
WAVE15_RESCUED = frozenset({12, 14, 27, 38, 68, 113, 164, 175, 245})


@pytest.mark.skipif(not os.path.exists(WAVE15_CORPUS),
                    reason="wave-15 corpus lives outside the public repo")
def test_image_gate_replays_the_stored_wave15_corpus():
    import json
    corpus = [json.loads(ln) for ln in open(WAVE15_CORPUS, encoding="utf-8")]
    assert len(corpus) == 56
    passed = {r["id"] for r in corpus
              if cp.cover_confirms(r["desc"], r["title"], r["author"])[0]}
    assert passed == WAVE15_OLD_PASS | WAVE15_RESCUED   # 9 rescues, 0 drift
    # the held-honestly class (DB-vs-cover divergence rows) still refused:
    for rid in (231, 701):
        row = next(r for r in corpus if r["id"] == rid)
        ok, why = cp.cover_confirms(row["desc"], row["title"], row["author"])
        assert not ok and "titelord" in why


# ---- the byte-pin battery (MC 12649 DoD) -------------------------------------
# Pre-existing, NON-hyphenated cases incl. the wrong-author set: the verdict
# table (ok + the exact refusal string — cover_pass writes it verbatim into
# the wave report) must be byte-identical pre/post the tolerance landing.
# COVER_CONFIRM_PIN below was generated against cover_confirms AT 859457f,
# BEFORE any change to scripts/cover_gates.py, by evaluating BATTERY against
# the pre-change gate in this exact checkout (command + output in the MC 12649
# evidence; regenerable with git show 859457f:scripts/cover_gates.py).

BATTERY = [
    ("true_cover", DESC_TRUE, BOOK["title"], BOOK["author"]),
    ("author_portrait", "En kvinna sitter i en soffa. Ingen text är tryckt "
                        "på bilden.", BOOK["title"], BOOK["author"]),
    ("wrong_book_same_author", "LOVISA STRAND — KARIN I DALARNA",
     BOOK["title"], BOOK["author"]),
    ("author_only_printed", "FJÄLLNYAN förlag, LOVISA STRAND",
     BOOK["title"], BOOK["author"]),
    ("wrong_author_printed", "DÄR LINGONRISEN SUSAR av KARIN SANDELL",
     BOOK["title"], BOOK["author"]),
    ("author_split_by_space", "DÄR LINGONRISEN SUSAR av FORFATTAREN STR "
     "ANDERSSON", BOOK["title"], BOOK["author"]),
    ("no_distinctive_words", "Av författaren Elsa Vide\nP.m.\nVide & Co",
     "P.M.", "Elsa Vide"),
    ("stopword_title", DESC_TRUE, "Av och till", "Lovisa Strand"),
    ("empty_desc", "", BOOK["title"], BOOK["author"]),
    ("empty_author_field", DESC_TRUE, BOOK["title"], ""),
    ("subtitle_partial", "LINGONRISEN — roman", BOOK["title"], BOOK["author"]),
    ("publisher_only", "BAZAR förlag", BOOK["title"], BOOK["author"]),
]

COVER_CONFIRM_PIN = """true_cover|True|titel+forfattare tryckta i bilden
author_portrait|False|bara 0/3 titelord tryckta i bilden
wrong_book_same_author|False|bara 0/3 titelord tryckta i bilden
author_only_printed|False|bara 0/3 titelord tryckta i bilden
wrong_author_printed|False|forfattare trycks inte i bilden
author_split_by_space|False|forfattare trycks inte i bilden
no_distinctive_words|False|titeln har inga sarskiljande ord
stopword_title|False|titeln har inga sarskiljande ord
empty_desc|False|bara 0/3 titelord tryckta i bilden
empty_author_field|True|titel+forfattare tryckta i bilden
subtitle_partial|False|bara 1/3 titelord tryckta i bilden
publisher_only|False|bara 0/3 titelord tryckta i bilden"""

def test_cover_confirms_verdict_table_is_byte_pinned():
    table = "\n".join(
        f"{name}|{ok}|{why}" for name, desc, title, author in BATTERY
        for ok, why in [cp.cover_confirms(desc, title, author)])
    assert table == COVER_CONFIRM_PIN


# ---- ranking -----------------------------------------------------------------

def test_isbn_in_url_outranks_everything_and_walls_never_appear():
    hits = [{"url": "https://blogg.example/x", "title": "Där lingonrisen susar"},
            {"url": "https://adlibris.com/b/9789173710176", "title": "…"},
            {"url": "https://witaj.example/doc.pdf", "title": "…"}]
    got = cp.rank_candidates(hits, BOOK["title"], ["9789173710176"],
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
    page = ('<html><head><title>Där lingonrisen susar - Lovisa Strand</title>'
            '<meta property="og:image" content="/bok.jpg"></head></html>')
    fetch = FakeFetch({"https://forlag.example/bok": page.encode(),
                       "https://forlag.example/bok.jpg": img_bytes()})
    row = cp.attempt_book(state, BOOK,
                          searcher=fake_search([{"url": "https://forlag.example/bok",
                                                 "title": "Där lingonrisen susar"}]),
                          fetch=fetch, describer=lambda b: DESC_TRUE)
    assert row["outcome"] == "covered" and row["cover_source"] == "manual-url"
    stored = state.execute("SELECT cover_path, cover_source FROM book WHERE id=1").fetchone()
    assert stored[1] == "manual-url" and stored[0] == "covers/1.jpg"
    assert (db.state_base() / "covers" / "1.jpg").exists()


def test_attempt_refuses_a_portrait_og_image_and_stores_nothing(state, tmp_path):
    page = ('<html><head><title>Där lingonrisen susar - Lovisa Strand</title>'
            '<meta property="og:image" content="/portrait.jpg"></head></html>')
    fetch = FakeFetch({"https://forfattare.example/bok": page.encode(),
                       "https://forfattare.example/portrait.jpg": img_bytes(1200, 800)})
    row = cp.attempt_book(state, BOOK,
                          searcher=fake_search([{"url": "https://forfattare.example/bok",
                                                 "title": "Där lingonrisen susar"}]),
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
          "title": "Karin i Dalarna"}], "Karin i Dalarna", [], set())
    assert got == ["https://bokborsen.example/view/Ahlstr%C3%B6m-Kristina/Hanna"]


def test_dark_vision_stores_nothing_and_reports_loudly(state):
    page = ('<html><head><title>Där lingonrisen susar - Lovisa Strand</title>'
            '<meta property="og:image" content="/bok.jpg"></head></html>')
    fetch = FakeFetch({"https://forlag.example/bok": page.encode(),
                       "https://forlag.example/bok.jpg": img_bytes()})
    row = cp.attempt_book(state, BOOK,
                          searcher=fake_search([{"url": "https://forlag.example/bok",
                                                 "title": "Där lingonrisen susar"}]),
                          fetch=fetch, describer=lambda b: None)
    assert row["outcome"] == "unresolved" and "vision morkt" in row["detail"]
    assert state.execute("SELECT cover_path FROM book WHERE id=1").fetchone()[0] is None


def test_a_429_host_is_blocked_and_never_retried_within_the_pass(state):
    hits = [{"url": "https://adlibris.com/b/1", "title": "Där lingonrisen susar"},
            {"url": "https://adlibris.com/b/2", "title": "Där lingonrisen susar"}]
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
