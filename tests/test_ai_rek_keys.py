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
                 or missing titel) and accepts the empty and full lists

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
reader-shape red on the garbage cases.
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
from tests.test_ai_rek_pass import (GRADERADE, FakeLane, FakePost, isbn,
                                    korpus_tsv, library_med_html, shelf_html,
                                    svar, svar_alla)

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
