"""MC 12616 (M11-N8a) — the /ai-rek door's FULL-SWAP generation mode
(PLAN §d completion) + the runner's opt-in envelope. The legs ride
test_ai_rek.py's fixture idiom VERBATIM (site/door/rec/csrf/count/_rid —
one mechanism, imported, never a copy):

* full-swap-deletes-absent  {"generation": [...]} is the COMPLETE new
  generation: state='new' rows absent from it are DELETED (deleted_n counts
  them), present rows refresh exactly as in upsert mode.
* decided-rows-never-deleted  accept/decline rows SURVIVE every sweep —
  absent, and present under an identity VARIANT (the isbn lane, the
  wish_key lane): the DELETE rides `state='new'`, the same guard as the
  fix-wave duppar merge, and identity is THE SAME union `_bok_rad` matches
  on (`_samma_bock`, one mechanism, cited).
* empty-generation-refused  a full-swap of ZERO rows is REFUSED fail-loud
  (400, named copy) with rows kept — mass-delete by an empty payload is the
  footgun the card names. The belt mirrors it inside ingest: a payload where
  EVERY row is shape-rejected (zero valid identities) sweeps NOTHING, loud
  via rejected_shape.
* upsert-byte-identical  no "generation" key ⇒ the answer carries exactly
  the six counters of today, no deleted_n key (the existing door legs stand
  green UNTOUCHED as the byte anchors of behaviour).
* posture-unchanged  the envelope changes the body vocabulary ONLY: the
  disarmed door still answers 503 writing nothing, wrong/absent token the
  SAME uniform 401 bytes as the plain array, GET keeps the guard's 302.

PLANTED-RED for this card is mapped in the commit body (red-first runs of
the new legs against the pre-change door + two mutants with sha-verified
restore).
"""
import json
import sqlite3

from tests.test_ai_rek import (TOKEN, _rid, count, csrf, door, rec, site)

# The EXACT counter keys the upsert answer carries TODAY (MC 12597 + the
# 12602 fix wave) — the key-set anchor of "byte-identical mode-off".
UPPSATTA_NYCKLAR = {"accepted", "inserted", "updated", "kept_accept",
                    "kept_decline", "rejected_shape"}


def door_gen(app, rows, token=TOKEN):
    """The runner-shaped full-swap POST: the generation envelope over the
    SAME rows vocabulary, its own client, no Origin (the curl posture)."""
    headers = {} if token is None else {"X-Ai-Rek-Token": token}
    return app.test_client().post("/liselott/ai-rek",
                                  json={"generation": rows}, headers=headers)


def states(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return {row[0]: row[1] for row in
                conn.execute("SELECT title, state FROM ai_rek ORDER BY id")}
    finally:
        conn.close()


# ── full-swap: absent `new` rows are deleted, present ones refresh ──────────
def test_full_swap_deletes_absent_new_rows(tmp_path, monkeypatch):
    app, owner = site(tmp_path, monkeypatch)
    r = door_gen(app, [rec(isbn13="9789190000007"),
                       rec("Bortagen", isbn13="9789190000008")])
    assert r.status_code == 200
    assert r.get_json()["inserted"] == 2
    assert r.get_json()["deleted_n"] == 0              # nothing absent yet
    r2 = door_gen(app, [rec(isbn13="9789190000007", reason="Uppdaterat skäl")])
    j = r2.get_json()
    assert j["updated"] == 1 and j["deleted_n"] == 1   # the absent one swept
    assert set(states(tmp_path / "liselott.db")) == {"Kappor på en hatt"}
    conn = sqlite3.connect(tmp_path / "liselott.db")
    assert conn.execute("SELECT reason FROM ai_rek").fetchone()[0] \
        == "Uppdaterat skäl"                           # present row refreshed
    conn.close()
    page = owner.get("/liselott/rekommendationer").get_data(as_text=True)
    assert "Bortagen" not in page                      # the sweep reaches the page


# ── the identity UNION guards the sweep, one mechanism with the matcher ─────
def test_full_swap_sweeps_only_rows_absent_from_the_identity_union(
        tmp_path, monkeypatch):
    """The live isbn-lane row survives a respelled generation (different
    title AND author, SAME isbn13 — rec_key differs, the isbn lane bites);
    the keyless row no identity of the payload reaches is deleted."""
    app, _ = site(tmp_path, monkeypatch)
    door(app, [rec(isbn13="9789190000007"), rec("Annat Verk")])
    r = door_gen(app, [rec("Helt Annan Titel", author_name="U. Känd",
                           isbn13="9789190000007"),
                       rec("Ny Fyra", isbn13="9789190000009")])
    j = r.get_json()
    assert j["updated"] == 1 and j["inserted"] == 1 and j["deleted_n"] == 1
    assert set(states(tmp_path / "liselott.db")) == {"Helt Annan Titel",
                                                     "Ny Fyra"}


def test_full_swap_never_deletes_accept_or_decline_incl_identity_variants(
        tmp_path, monkeypatch):
    """PLAN §d's NEVER: the sweep touches state 'new' ONLY. A declined and
    an accepted row stay put while the generation that omits them sweeps
    everything else; and a decided row re-arriving under a DIFFERENT
    identity (keyless → isbn lane) is kept_declined on the same row, never
    deleted, never re-decided."""
    app, owner = site(tmp_path, monkeypatch)
    door(app, [rec(),                                    # A: keyless, declined
               rec("Accepterad Bok", isbn13="9789190000008"),   # B: accepted
               rec("Försvinn", isbn13="9789190000009")])        # C: swept
    ids = {row[0] for row in _rid(tmp_path / "liselott.db")}
    titel_id = {}
    conn = sqlite3.connect(tmp_path / "liselott.db")
    for rid, titel in conn.execute("SELECT id, title FROM ai_rek"):
        titel_id[titel] = rid
    conn.close()
    tk = csrf(owner)
    assert owner.post(f"/liselott/ai-rek/{titel_id['Kappor på en hatt']}"
                      f"/decline", data={"csrf": tk}).status_code == 302
    assert owner.post(f"/liselott/ai-rek/{titel_id['Accepterad Bok']}"
                      f"/accept", data={"csrf": tk}).status_code == 302
    r = door_gen(app, [rec("Ny Generation", isbn13="9789190000010")])
    j = r.get_json()
    assert j["deleted_n"] == 1                          # only C, the 'new' one
    st = states(tmp_path / "liselott.db")
    assert st["Kappor på en hatt"] == "decline"         # absent, still there
    assert st["Accepterad Bok"] == "accept"             # absent, still there
    assert "Försvinn" not in st
    # the identity VARIANT of the declined book arrives WITH an isbn (the
    # other payload row keeps "Ny Generation" PRESENT — the sweep bites on
    # absence ONLY):
    r2 = door_gen(app, [rec(isbn13="9789190000011"),
                        rec("Ny Generation", isbn13="9789190000010")])
    assert r2.get_json()["kept_decline"] == 1
    assert r2.get_json()["deleted_n"] == 0
    st = states(tmp_path / "liselott.db")
    assert st["Kappor på en hatt"] == "decline"         # same row, untouched
    conn = sqlite3.connect(tmp_path / "liselott.db")
    assert conn.execute("SELECT isbn13 FROM ai_rek WHERE title = ?",
                        ("Kappor på en hatt",)).fetchone()[0] is None
    conn.close()
    assert len(ids) == 3 and len(_rid(tmp_path / "liselott.db")) == 3


# ── the empty-generation refusal + the zero-valid-rows belt ─────────────────
def test_full_swap_empty_generation_is_refused_rows_kept(tmp_path, monkeypatch):
    """Fail-loud, rows kept: zero rows is NOT an empty complete generation,
    it is a footgun — the door refuses it BEFORE touching the DB and the
    copy names the rule."""
    app, _ = site(tmp_path, monkeypatch)
    door(app, [rec(isbn13="9789190000007")])
    r = door_gen(app, [])
    assert r.status_code == 400
    body = r.get_data(as_text=True)
    assert "Generationen är tom" in body
    assert door_gen(app, []).get_data(as_text=True) == body   # one uniform copy
    assert count(tmp_path / "liselott.db", "SELECT COUNT(*) FROM ai_rek") == 1


def test_full_swap_zero_valid_rows_sweeps_nothing(tmp_path, monkeypatch):
    """The belt INSIDE ingest: 500 shape-garbage rows are zero VALID
    identities — rejected_shape answers loudly, deleted_n stays 0, the live
    rows stand. (The door 400s the literal []; this leg pins that garbage
    can never ride the sweep either.)"""
    app, _ = site(tmp_path, monkeypatch)
    door(app, [rec(isbn13="9789190000007")])
    r = door_gen(app, [{"title": "", "reason": "x", "source": "y"}
                       for _ in range(5)])
    j = r.get_json()
    assert j["rejected_shape"] == 5 and j["deleted_n"] == 0
    assert count(tmp_path / "liselott.db", "SELECT COUNT(*) FROM ai_rek") == 1


# ── mode-off stays byte-identical; the envelope never shifts the posture ────
def test_upsert_answer_carries_no_deleted_n(tmp_path, monkeypatch):
    """Mode OFF = today's answer exactly: the six counter keys, no
    deleted_n. (The behaviour anchors are the EXISTING test_ai_rek legs,
    green UNTOUCHED — this leg pins the key-set the byte-anchor runs on.)"""
    app, _ = site(tmp_path, monkeypatch)
    r = door(app, [rec(isbn13="9789190000007")])
    j = r.get_json()
    assert set(j) == UPPSATTA_NYCKLAR and "deleted_n" not in j
    g = door_gen(app, [rec("Generation", isbn13="9789190000008")]).get_json()
    assert set(g) == UPPSATTA_NYCKLAR | {"deleted_n"}
    assert json.dumps(j, sort_keys=True).find("deleted_n") == -1


def test_generation_envelope_on_the_disarmed_door_is_503_writing_nothing(
        tmp_path, monkeypatch):
    """Credential FIRST, envelope second: a generation POST on the un-armed
    door is the SAME generic 503 (owner session included) with zero rows —
    the sweep never runs behind a refused credential."""
    app, owner = site(tmp_path, monkeypatch, token=None)
    assert door_gen(app, [rec()], token=None).status_code == 503
    assert owner.post("/liselott/ai-rek",
                      json={"generation": [rec()]}).status_code == 503
    assert count(tmp_path / "liselott.db", "SELECT COUNT(*) FROM ai_rek") == 0


def test_generation_envelope_wrong_token_is_the_same_uniform_401(
        tmp_path, monkeypatch):
    """No new copy, no oracle: the envelope with a wrong token answers THE
    SAME 401 bytes the plain array gets, and nothing is written."""
    app, _ = site(tmp_path, monkeypatch)
    wrong = door_gen(app, [rec()], token="b" * 64)
    array_wrong = door(app, [rec()], token="b" * 64)
    assert wrong.status_code == 401
    assert wrong.get_data(as_text=True) == array_wrong.get_data(as_text=True)
    assert count(tmp_path / "liselott.db", "SELECT COUNT(*) FROM ai_rek") == 0
