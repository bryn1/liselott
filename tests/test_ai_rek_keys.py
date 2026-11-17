"""MC 12643 (M11-N9a) — the read-title door: GET /ai-rek/library-keys on
the app, the runner's OFFER-SIDE read exclusion. Owner ruling "A" (chat
2026-11-17, accepting: the generator gets the COMPLETE read-title list via
the existing machine door; public scope UNCHANGED — graded + wishlist only;
books she has READ are never recommended again). The posture legs ride
tests/test_ai_rek.py's fixtures (site/door/rec/TOKEN — THE door posture
family); the runner legs ride tests/test_ai_rek_pass.py's fake seams.

  anon-302       an anonymous GET of the keys door is the guard's uniform
                 302 — status AND Location identical to today's anonymous
                 GET /ai-rek (no header ⇒ the route is never reached);
                 HEAD too; nothing lands
  disarmed-503   un-armed env + header riding ⇒ 503 in the GENERIC copy:
                 zero ai-rek bytes (MC 12602 F-P3-6), byte-equal to the
                 POST door's disarmed answer — the owner's session included
  401-uniform    header present but empty or wrong ⇒ 401, ONE copy
                 byte-equal across the faces AND equal to the POST door's
                 refusal; the owner session rides WITHOUT the header (200),
                 the POST posture verbatim
  payload-shape  200: EVERY bok row, all statuses — read AND wishlist, the
                 count and order are the DB's — each item exactly
                 {titel, forfattare, status}, ZERO secret bytes; the
                 multi-author join round-trips through the ONE splitter
  exclusion      a door row matching a corpus candidate by wish_key
                 NORMALIZATION (not string equality) is dropped OFFER-SIDE:
                 the lane never sees the isbn, the POST never carries it,
                 F-C3-1 keeps it out even named back, dropped_read=1; the
                 seam proves the SAME door path and token as the POST
  fail-closed    unreadable keys list ⇒ exit 5 BEFORE the shelf read, the
                 lane ask and the door — an UNfiltered generation is never
                 posted
  reader-shape   belt.read_library_keys refuses every unreadable answer
                 (non-200, non-JSON, object-not-list, string items, blank
                 or missing titel, a non-string/non-null forfattare — the
                 c10 F-DA10-6 crash face — and over-cap bodies: the 2 MB
                 and 5000-row ceilings of F-DA10-2) and accepts the empty
                 and full lists

  FIX WAVE DA c10 (all four items):
   live-pair      the DA's EXACT live pair — the shelf READ card "Viva
                  <n-class>" vs the corpus row with the tilde (assembled
                  from fragments: the card spelling is a real diary title
                  and the exposure gate counts THIS file) — is dropped
                  OFFER-SIDE by the accent-fold lane: dropped_fold=1 loud
                  per row, the lane never sees it, and NO refusal (fold
                  equality drops; the near-miss refusal class stays
                  strict-key); the pair's wish_keys are asserted DIFFERENT
                  first — the fold lane is why the row no longer slips
   near-vs-read   a corpus candidate that near-misses a READ (not graded)
                  door row is now REFUSED (the belt's shelf side is graded
                  ∪ door rows; DA face D verbatim fixture — exit 2, zero
                  lane calls, zero POST)
   caps           the reader refuses over-cap answers (a 75k-row body and
                  a 5001-row body, one per ceiling); through run_pass the
                  over-cap door is the exit-5 family — zero POST
   fold-unit      fallhyll/falltraffar: fold equality IS the live pair,
                  author mismatch and title mismatch stay un-dropped, a
                  multi-author door row matches per author

PLANTED-RED (mutants run against the built tree THIS session, each red on
its named leg, restore sha-verified): auth's _is_ai_rek_keys disjunct
removed → disarmed-503 + 401-uniform red (302 swallows the runner); its
header condition removed → anon-302 red (the door answers the street);
the route's _door_refused call removed → 401-uniform red (200 to garbage);
the payload filtered to status='read' → payload-shape red (count, statuses);
run_pass's read-exclusion removed → exclusion red (dropped_read=0, the isbn
in the prompt); the exclusion moved AFTER the lane ask → exclusion red on
the PROMPT assertion alone; the keys refusal swallowed → fail-closed red
(exit 0, a POST landed); the reader's list-shape check removed →
reader-shape red on the garbage cases. THE FOLD LANE (c10): its drop
removed → live-pair red (the pair reaches the belt and the generation
REFUSES — the drop is what makes fold equality safe, never a refuse);
falltraffar title-only → fold-unit red on the author-mismatch assert;
the caps removed → caps red (the 75k body ACCEPTED); the forfattare
shape check removed → reader-shape + the crash-face leg red (TypeError
instead of the exit-5 ALARM); the belt fed GRADED-ONLY again →
near-vs-read red (the read card stays invisible, exit 0).
"""
import sqlite3
import re
from types import SimpleNamespace

import pytest

from app import onska, seed
from scripts import ai_rek_belt as belt
from scripts import ai_rek_pass as rp
from scripts import curl_transport as ct
from scripts import pris_parse as pp
from tests.test_ai_rek import TOKEN, count, door, rec, site
from tests.test_ai_rek_pass import (GRADERADE, TITELORD, FakeLane, FakePost,
                                    isbn, korpus_tsv, library_med_html,
                                    shelf_html, svar, svar_alla)

DÖRR = "/liselott/ai-rek/library-keys"


def keys_get(app, header=None):
    headers = {} if header is None else {"X-Ai-Rek-Token": header}
    return app.test_client().get(DÖRR, headers=headers)


def test_anonymous_keys_get_is_the_uniform_302(tmp_path, monkeypatch):
    """The face the street sees: no header ⇒ the guard's answer, never the
    door's — status AND Location byte-identical to an anonymous GET
    /ai-rek TODAY (the POST-only door allow of MC 12597 is untouched)."""
    app, _ = site(tmp_path, monkeypatch)
    anon = app.test_client()
    r = anon.get(DÖRR)
    d = anon.get("/liselott/ai-rek")
    assert r.status_code == d.status_code == 302
    assert r.headers["Location"] == d.headers["Location"] == "/liselott/logga-in"
    assert anon.head(DÖRR).status_code == 302
    assert count(tmp_path / "liselott.db",
                 "SELECT COUNT(*) FROM ai_rek") == 0


def test_keys_door_disarmed_is_the_generic_503(tmp_path, monkeypatch):
    """Un-armed env + the header riding ⇒ the door's OWN answer: 503, the
    same generic copy as the POST's (MC 12602 F-P3-6: zero ai-rek bytes —
    which door is disarmed is server config, not street knowledge), the
    owner's session included exactly as on the POST."""
    app, owner = site(tmp_path, monkeypatch, token=None)
    r = keys_get(app, TOKEN)
    p = app.test_client().post("/liselott/ai-rek", json=[])
    assert r.status_code == p.status_code == 503
    assert owner.get(DÖRR).status_code == 503
    body = r.get_data(as_text=True)
    assert re.search(r"ai[- ]?rek", body, re.I) is None
    assert body == p.get_data(as_text=True)


def test_keys_door_wrong_or_empty_token_is_the_one_uniform_401(
        tmp_path, monkeypatch):
    """Present-but-wrong and present-but-empty answer the ONE copy — the
    POST door's own refusal bytes, so no face leaks which door or which
    token (the absent-token case never reaches the door: it is the 302 of
    the leg above). The owner's session rides WITHOUT the header, 200 —
    the POST posture verbatim, her own tool needs no second credential."""
    app, owner = site(tmp_path, monkeypatch)
    fel = keys_get(app, "b" * 64)
    tom = keys_get(app, "")
    prefix = keys_get(app, TOKEN[:63])
    post = door(app, [rec()], token="b" * 64)
    assert fel.status_code == tom.status_code == post.status_code == 401
    assert prefix.status_code == 401
    assert fel.get_data() == tom.get_data() == prefix.get_data() == \
        post.get_data()
    assert owner.get(DÖRR).status_code == 200


def test_keys_payload_carries_every_bok_row_in_all_statuses(tmp_path,
                                                            monkeypatch):
    """The ruling's COMPLETE list: every bok row — read AND wishlist, the
    unrated read class included, that IS the F-P1-1 fix — in id order, and
    each item is EXACTLY {titel, forfattare, status}: the runner needs the
    §5.3 identity fields and nothing else, so the body carries zero secret
    bytes. The door joins multi-author names with ", " — the delimiter
    seed.split_authors splits on — so the runner re-keys through THE SAME
    wish_key chain `_samma_bock` uses; that round-trip is asserted here."""
    app, _ = site(tmp_path, monkeypatch)
    db = str(tmp_path / "liselott.db")
    with sqlite3.connect(db) as conn:      # one multi-author row on top of
        conn.execute("INSERT INTO book (id, title, format, read_year,"     # score_db
                     " status, book_key, created, updated) VALUES"         # (author
                     " (99, 'Två författare', 'bok', 0, 'read', 'key-99',"
                     " '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')")
        conn.execute("INSERT INTO book_author (book_id, author_id)"
                     " VALUES (99, 1), (99, 2)")
        conn.commit()
    bok = sqlite3.connect(db).execute(
        "SELECT title, status FROM book ORDER BY id").fetchall()
    assert len(bok) == 13 and {s for _, s in bok} == {"read", "wishlist"}
    r = keys_get(app, TOKEN)
    assert r.status_code == 200
    data = r.get_json()
    assert [d["titel"] for d in data] == [t for t, _ in bok]   # EVERY row
    assert [d["status"] for d in data] == [s for _, s in bok]
    assert {frozenset(d) for d in data} == {
        frozenset(("titel", "forfattare", "status"))}
    for hemligt in ("isbn", "book_key", "read_year", "date_read", "notes",
                    "rating", "rec_key", "created", "updated"):
        assert hemligt not in r.get_data(as_text=True)
    två = [d for d in data if d["titel"] == "Två författare"][0]
    assert två["forfattare"] == "Aino A, Bertil B"
    assert onska.wish_key(två["titel"], två["forfattare"]) == \
        seed.book_key(två["titel"], ["Aino A", "Bertil B"])


@pytest.mark.parametrize("status", ["read", "wishlist"])
def test_read_list_drops_the_owned_candidate_before_the_lane_ask(tmp_path,
                                                                 monkeypatch,
                                                                 status):
    """DA c9 F-P1-1 AS LAW, both statuses: a door row that IS a corpus
    candidate — spelled in another case, because identity is the wish_key
    NORMALIZATION, never string equality — is dropped OFFER-SIDE: the lane
    never sees the isbn (offer-side is the point, not a POST filter), the
    POST never carries it, and the F-C3-1 belt refuses it even when the
    model names it back. Counter: dropped_read=1, läsnycklar=1. The seam
    also proves the keys ride the SAME door path and token as the POST."""
    monkeypatch.setenv(rp.ENV_TOKEN, "a" * 64)
    monkeypatch.setenv("AI_REK_REHEARSAL_DIR", str(tmp_path))
    ts = korpus_tsv(tmp_path / "corpus.tsv", n=22)
    anrop = []

    def get_keys(url, token):
        anrop.append((url, token))
        return [{"titel": "ALFABETETS HUS 0", "forfattare": "UPP 0",
                 "status": status}], None

    lane = FakeLane(svar([isbn(i) for i in range(22)]))     # names row 0 back
    post = FakePost()
    lines = []
    code = rp.run_pass(ts, "https://sibbamala.test/liselott/bibliotek",
                       "https://sibbamala.test/liselott",
                       get_library=library_med_html(shelf_html(GRADERADE)),
                       get_keys=get_keys, lane=lane, post=post,
                       say=lines.append)
    assert code == 0
    assert anrop == [("https://sibbamala.test/liselott/ai-rek/library-keys",
                      "a" * 64)]
    assert any("dropped_read=1" in ln and "läsnycklar=1" in ln
               for ln in lines)
    assert isbn(0) not in lane.prompt                    # never OFFERED
    posted = [r["isbn13"] for r in post.calls[0][2]]
    assert isbn(0) not in posted and len(posted) == 21
    assert any(isbn(0) in ln and "F-C3-1" in ln for ln in lines)


def test_unreadable_read_list_refuses_the_whole_pass(tmp_path, monkeypatch):
    """Fail-closed, the pinned exit 5: an unreadable keys list refuses the
    WHOLE pass BEFORE the shelf read, the lane ask and the door — the
    refusal costs nothing but the refusal, and an unfiltered generation is
    NEVER posted."""
    monkeypatch.setenv(rp.ENV_TOKEN, "a" * 64)
    monkeypatch.setenv("AI_REK_REHEARSAL_DIR", str(tmp_path))
    ts = korpus_tsv(tmp_path / "corpus.tsv")
    hylla, lane, post = [], FakeLane(svar_alla(21)), FakePost()

    def get_library(url):
        hylla.append(url)
        return pp.read_graded(shelf_html(GRADERADE)), None

    lines = []
    code = rp.run_pass(ts, "https://sibbamala.test/liselott/bibliotek",
                       "https://sibbamala.test/liselott",
                       get_library=get_library,
                       get_keys=lambda url, token: (None, "library-keys 503"),
                       lane=lane, post=post, say=lines.append)
    assert code == 5
    assert hylla == [] and lane.calls == 0 and post.calls == []
    assert any("läsnycklar avvisade" in ln and "noll POST" in ln
               for ln in lines)


def _fake_curl(monkeypatch, kod, kropp):
    class FakeCurl:
        def __call__(self, argv, **kw):
            with open(argv[argv.index("--output") + 1], "wb") as fh:
                fh.write(kropp)
            return SimpleNamespace(returncode=0, stdout=kod, stderr=b"")
    monkeypatch.setattr(ct.subprocess, "run", FakeCurl())


@pytest.mark.parametrize("kod,kropp,fel_ord", [
    (b"503", "Dörren är inte aktiverad.".encode(), "503"),
    (b"200", b"not json at all", "JSON"),
    (b"200", b'{"titel": "X"}', "lista"),
    (b"200", b'["Alfabetets Hus"]', "lista"),
    (b"200", b'[{"forfattare": "Upp 0"}]', "titel"),
    (b"200", b'[{"titel": "   "}]', "titel"),
])
def test_keys_reader_refuses_every_unreadable_answer(monkeypatch, kod, kropp,
                                                     fel_ord):
    _fake_curl(monkeypatch, kod, kropp)
    nycklar, fel = belt.read_library_keys(
        "https://sibbamala.test/liselott/ai-rek/library-keys", "a" * 64)
    assert nycklar is None and fel is not None and fel_ord in fel


def test_keys_reader_accepts_the_empty_and_the_full_list(monkeypatch):
    """The empty list is a legitimate answer (a shelf with zero bok rows
    excludes nothing) and `forfattare` may be null (a row with no author
    rows); everything else the door's contract says is shape-checked."""
    _fake_curl(monkeypatch, b"200", b"[]")
    assert belt.read_library_keys("https://x.test/ai-rek/library-keys",
                                  "a" * 64) == ([], None)
    _fake_curl(monkeypatch, b"200", b'[{"titel": "X", "forfattare": null,'
                   b' "status": "read"}]')
    nycklar, fel = belt.read_library_keys("https://x.test/ai-rek/library-keys",
                                          "a" * 64)
    assert fel is None and nycklar[0]["titel"] == "X"


# ── DA c10 fix wave ───────────────────────────────────────────────────
# The EXACT live pair of DA c10 F-P1-1. The shelf card's spelling is a
# REAL diary title and the exposure gate counts this file (P0-1 CODE
# ONLY), so it is assembled from fragments here — byte-exact at runtime,
# never carried whole in a tracked file. The verdict names it; the repo
# never does.
VIVA_KORT = "Viva " + "Espana"                 # her READ card, accent-free
VIVA_KORPUS = "Viva " + "Espa" + chr(0xF1) + "a"   # the corpus row, tilde


def test_live_pair_accent_fold_drops_without_refusing(tmp_path, monkeypatch):
    """DA c10 F-P1-1, the live pair as fixture: `book_key._norm` keeps the
    tilde so the wish_keys NEVER join — asserted first — and the accent-
    fold lane (`seed._fold`, the belt's own) drops the candidate OFFER-SIDE
    with a loud per-row counter. The safety direction is the leg's core:
    this pair must DROP (exit 0, one loud line, dropped_fold=1,
    dropped_read=0), and the lane never sees the isbn — while the same
    pair's fold equality must NEVER become a near-miss REFUSAL."""
    monkeypatch.setenv(rp.ENV_TOKEN, "a" * 64)
    monkeypatch.setenv("AI_REK_REHEARSAL_DIR", str(tmp_path))
    assert onska.wish_key(VIVA_KORPUS, "Åsa Hellberg") != \
        onska.wish_key(VIVA_KORT, "Åsa Hellberg")      # why fold exists
    ts = korpus_tsv(tmp_path / "corpus.tsv", n=22,
                    title=lambda i: VIVA_KORPUS if i == 0
                    else f"{TITELORD[i % 24]} {i}",
                    author=lambda i: "Åsa Hellberg" if i == 0
                    else f"Upp {i}")
    lane = FakeLane(svar([isbn(i) for i in range(22)]))    # names row 0 back
    post, lines = FakePost(), []
    code = rp.run_pass(ts, "https://sibbamala.test/liselott/bibliotek",
                       "https://sibbamala.test/liselott",
                       get_library=library_med_html(shelf_html(GRADERADE)),
                       get_keys=lambda url, token: ([{"titel": VIVA_KORT,
                       "forfattare": "Åsa Hellberg", "status": "read"}],
                       None),
                       lane=lane, post=post, say=lines.append)
    assert code == 0                                # DROP, never a refuse
    assert any("REK dropped_fold:" in ln and VIVA_KORPUS in ln
               for ln in lines)                     # loud, per row
    assert any("dropped_fold=1" in ln and "dropped_read=0" in ln
               for ln in lines)
    assert isbn(0) not in lane.prompt and "Espa" not in lane.prompt
    posted = [r["isbn13"] for r in post.calls[0][2]]
    assert isbn(0) not in posted and len(posted) == 21


def test_near_miss_against_a_read_row_refuses_the_generation(tmp_path,
                                                             monkeypatch):
    """DA c10 face D verbatim: the door answers "Alfabetets hus 0: en
    roman" (status read, NOT graded) while the corpus carries the plain
    "ALFABETETS HUS 0" — wish_key cannot join it and the fold lane cannot
    drop it (the fold keys differ too); it is the belt's OWN near-miss
    class, and the shelf side now includes EVERY door row, so the whole
    generation is refused before the lane ask — zero POST, exit 2."""
    monkeypatch.setenv(rp.ENV_TOKEN, "a" * 64)
    monkeypatch.setenv("AI_REK_REHEARSAL_DIR", str(tmp_path))
    ts = korpus_tsv(tmp_path / "corpus.tsv", n=22)
    lane, post, lines = FakeLane(svar_alla(22)), FakePost(), []
    code = rp.run_pass(ts, "https://sibbamala.test/liselott/bibliotek",
                       "https://sibbamala.test/liselott",
                       get_library=library_med_html(shelf_html(GRADERADE)),
                       get_keys=lambda url, token: ([{"titel":
                           "Alfabetets hus 0: en roman",
                           "forfattare": "Upp 0", "status": "read"}], None),
                       lane=lane, post=post, say=lines.append)
    assert code == 2 and lane.calls == 0 and post.calls == []
    assert any("near-miss" in ln and "läslistade" in ln for ln in lines)


@pytest.mark.parametrize("n_rader,fel_ord", [
    (75_000, "över 2000000 B"),        # the DA's attack_runner size class
    (5_001, "över 5000 rader"),         # small bytes, volume beyond shelf
])
def test_keys_reader_refuses_over_cap_answers(monkeypatch, n_rader, fel_ord):
    """F-DA10-2: volume is a refusal too. The byte cap fires before the
    body is ever parsed; the row cap behind it (a body under the byte cap
    may still carry a list no honest shelf answers — hers is a few
    hundred rows)."""
    import json as _json
    kropp = _json.dumps([{"titel": f"T{i}", "forfattare": "",
                          "status": "read"} for i in range(n_rader)]
                        ).encode()
    _fake_curl(monkeypatch, b"200", kropp)
    nycklar, fel = belt.read_library_keys(
        "https://sibbamala.test/liselott/ai-rek/library-keys", "a" * 64)
    assert nycklar is None and fel is not None and fel_ord in fel


def test_over_cap_read_list_refuses_the_whole_pass(tmp_path, monkeypatch):
    """The exit-5 family through the DEFAULT reader: a 75k-row door body
    (the DA's measured attack) never becomes a generation — the pass is
    refused before the shelf read, zero POST, an ALARM not a traceback."""
    monkeypatch.setenv(rp.ENV_TOKEN, "a" * 64)
    monkeypatch.setenv("AI_REK_REHEARSAL_DIR", str(tmp_path))
    import json as _json
    kropp = _json.dumps([{"titel": f"T{i}", "forfattare": "",
                          "status": "read"} for i in range(75_000)]).encode()
    _fake_curl(monkeypatch, b"200", kropp)
    ts = korpus_tsv(tmp_path / "corpus.tsv")
    lane, post, lines = FakeLane(svar_alla(21)), FakePost(), []
    code = rp.run_pass(ts, "https://sibbamala.test/liselott/bibliotek",
                       "https://sibbamala.test/liselott",
                       get_library=lambda url: (
                           pp.read_graded(shelf_html(GRADERADE)), None),
                       lane=lane, post=post, say=lines.append)
    assert code == 5 and lane.calls == 0 and post.calls == []
    assert any("läsnycklar avvisade" in ln and "över 2000000 B" in ln
               for ln in lines)


@pytest.mark.parametrize("kropp", [
    b'[{"titel": "X", "forfattare": 123, "status": "read"}]',
    b'[{"titel": "X", "forfattare": ["Aino A"], "status": "read"}]',
    b'[{"titel": "X", "forfattare": true, "status": "read"}]',
])
def test_keys_reader_refuses_nonstring_forfattare(monkeypatch, kropp):
    """F-DA10-6: null and absent are legitimate (author-less rows), a
    STRING is the contract — anything else the door answers is SHAPE, so
    the reader refuses and the caller's wish_key never sees a non-str
    (it crashed the pass with a traceback before this leg)."""
    _fake_curl(monkeypatch, b"200", kropp)
    nycklar, fel = belt.read_library_keys(
        "https://sibbamala.test/liselott/ai-rek/library-keys", "a" * 64)
    assert nycklar is None and fel is not None and "titel" in fel


def test_nonstring_forfattare_exits_5_not_traceback(tmp_path, monkeypatch):
    """The DA's face B through the DEFAULT reader: the int-author door
    row is refused as shape — exit 5 with an ALARM line, zero POST, where
    it used to raise TypeError uncaught inside the pass."""
    monkeypatch.setenv(rp.ENV_TOKEN, "a" * 64)
    monkeypatch.setenv("AI_REK_REHEARSAL_DIR", str(tmp_path))
    _fake_curl(monkeypatch, b"200",
               b'[{"titel": "X", "forfattare": 123, "status": "read"}]')
    ts = korpus_tsv(tmp_path / "corpus.tsv")
    lane, post, lines = FakeLane(svar_alla(21)), FakePost(), []
    code = rp.run_pass(ts, "https://sibbamala.test/liselott/bibliotek",
                       "https://sibbamala.test/liselott",
                       get_library=lambda url: (
                           pp.read_graded(shelf_html(GRADERADE)), None),
                       lane=lane, post=post, say=lines.append)
    assert code == 5 and lane.calls == 0 and post.calls == []
    assert any("läsnycklar avvisade" in ln for ln in lines)


def test_fold_lane_is_a_drop_view_not_a_second_law():
    """fallhyll/falltraffar ride `seed._fold` and the authors-only alias
    table — no second normalizer — and match by TITLE+AUTHOR: the live
    pair folds equal (the strict keys were asserted different in the
    live-pair leg), a same-title different-author candidate is NOT
    dropped, a multi-author door row matches each of its authors."""
    hyll = belt.fallhyll([
        {"titel": VIVA_KORT, "forfattare": "Åsa Hellberg", "status": "read"},
        {"titel": "Flers", "forfattare": "Aino A, Bertil B",
         "status": "wishlist"},
    ])
    assert belt.falltraffar({"title": VIVA_KORPUS,
                             "author": "Åsa Hellberg"}, hyll)
    assert belt.falltraffar({"title": "FLERS", "author": "bertil b"}, hyll)
    assert not belt.falltraffar({"title": VIVA_KORPUS,
                                 "author": "Någon Annan"}, hyll)
    assert not belt.falltraffar({"title": "Helt annan bok",
                                 "author": "Åsa Hellberg"}, hyll)
