"""MC 12617 (M11-N8b) — the generation GATE legs of the ai_rek runner:
split off tests/test_ai_rek_pass.py (the 600-line test ceiling; fixtures
and the MC 12601-era legs stay there and are imported here — the same
fixture-sharing idiom as tests/test_e2e / test_door_transport.py).

  prompt split         MC 12617 (DA c3 F-P3-4): the ask rides as a SYSTEM
                       instruction turn + a USER data turn; the answer
                       contract is BYTE-identical to MC 12601's (sha-
                       pinned) and rides the system turn; graded cards +
                       review quotes ride the user turn as data
  near-miss gate       MC 12617 (DA c3 F-P2-2c): a candidate that LOOKS
                       like a graded shelf card but cannot join (subtitle-
                       tail / 'del N' spellings) refuses the WHOLE
                       generation before the lane ask — the classifier
                       is scripts/ai_rek_belt's, shared with the corpus
                       rebase; the green leg is the rebase's DoD in code
  rehearsal belt       MC 12617 (DA c5 F-P4-1): --full refuses WITHOUT a
                       completed --dry-run of the same corpus against
                       the same library in the window (zero shelf reads,
                       zero lane asks, zero POSTs); the dry-run's stamp
                       authorizes one --full; stale window / changed
                       corpus / changed library re-refuse; the plain
                       upsert mode never needs a stamp (MC 12616's
                       default path byte-identical)
"""
import hashlib
import json

from scripts import ai_rek_belt as belt
from scripts import ai_rek_pass as rp
from tests.test_ai_rek_pass import (FakePost, GRADERADE, FakeLane, TITELORD,
                                    korpus_tsv, library_med_html, shelf_html,
                                    svar_alla)
from tests.test_ai_rek_pass import kör

# --- MC 12617 (M11-N8b): prompt split, near-miss gate, rehearsal belt ----

import hashlib


# The answer contract, BYTE-PINNED from MC 12601's one-turn prompt (git
# 157fb938 — extracted by RUNNING the shipped build_prompt; the first
# assert below checks this literal's sha, so a drifted copy goes red on
# its own before it can false-green anything else).
KONTRAKT = (
    "Ranka VARJE kandidat efter hur väl den passar smakprofilen. Motivera\n"
    "varje fit uttryckligen ur profilen: nämn vilka betygsatta böcker, genrer\n"
    "eller teman bedömningen vilar på (\"baserat på dina betyg på X\"-\n"
    "formuleringar).\n"
    "\n"
    "Svara med EXAKT en JSON-array — ingen text före eller efter, inga\n"
    "markdownstängsel:\n"
    "[{\"isbn13\": \"<13 siffror, ordgrant ur corpus>\", \"fit\": <flyttal 0.0–1.0>,\n"
    "  \"reason\": \"<motivering på svenska, 1–3 meningar>\"}, ...]\n"
    "\n"
    "Ordna fallande fit. Använd ENDAST isbn13-värden som finns ordgrant i\n"
    "corpus ovan.\n")
KONTRAKT_SHA256 = "79ac40b5929bd090cb80113264b0b9d03844a91303a4fd45a91354857ba9cae0"


def test_prompt_split_system_data_and_byte_identical_contract(tmp_path,
                                                              monkeypatch):
    """DA c3 F-P3-4: her graded cards and the review quotes are DATA —
    they ride the USER turn, away from the instructions; the SYSTEM turn
    carries the instructions and says out loud that the data is not
    instructions. The OUTPUT CONTRACT is byte-identical to MC 12601's
    (sha-pinned): what moved is placement, never wording — the reason
    field still must cite HER OWN graded books."""
    assert hashlib.sha256(KONTRAKT.encode("utf-8")).hexdigest() == \
        KONTRAKT_SHA256
    code, lines, lane, _ = kör(monkeypatch, tmp_path)
    assert code == 0
    system, user = lane.turer                         # the raw PAIR
    assert system.startswith("Du är rekommendationsmotorn")
    assert "UNDERLAG, inte" in system                 # data-not-
    assert "=== KANDIDATER" not in system             #   instructions frame
    assert KONTRAKT in system                         # the byte-pin rides
    assert "=== LISELOTTS BETYGSATTA BIBLIOTEK (smakprofilen) ===" in user
    assert "quote 0" in user and "quote 0" not in system


def test_lane_ask_carries_system_and_user_messages(monkeypatch):
    """The wire shape of the split: a (system, user) PAIR becomes ONE
    system + ONE user message; a plain str keeps the single user message
    MC 12601 shipped (the seam's legacy shape — the lane-timeout legs
    ride it)."""
    import urllib.request

    payloads = []

    class Svar:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"choices": [{"message":
                                            {"content": "[]"}}]}).encode()

    def fake_urlopen(req, timeout=None):
        payloads.append(json.loads(req.data.decode("utf-8")))
        return Svar()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert rp.lane_ask(("SYSTEMTEXT", "ANVÄNDART")) == "[]"
    msg = payloads[-1]["messages"]
    assert [m["role"] for m in msg] == ["system", "user"]
    assert (msg[0]["content"] == "SYSTEMTEXT"
            and msg[1]["content"] == "ANVÄNDART")
    assert rp.lane_ask("gamla enkla") == "[]"
    assert [m["role"] for m in payloads[-1]["messages"]] == ["user"]


def test_near_miss_candidate_refuses_whole_generation(tmp_path, monkeypatch):
    """THE F-P2-2c class, reproduced with SYNTHETIC names (the
    exposure gate counts this file — the real measured pair is named
    nowhere here): the shelf grades 'Simulantiegolna' 5★, the corpus
    carries 'Simulantiegolna (De Simulerade)' — wish_key CANNOT join
    them (seed.book_key alias-resolves authors only), so the row is an
    ownership ambiguity: the WHOLE generation refuses BEFORE the lane ask
    (lane 0 calls, post 0 calls, exit 2). No alias, no fuzzy key, no
    recommendation of a book she has already graded. The refused titles
    never ride stdout (the delivery posture: counts in the ALARM)."""
    graded = [{"title": "Simulantiegolna",
               "author": "Simulanda Simulandersson", "rating": 5}]
    ts = korpus_tsv(tmp_path / "corpus.tsv", n=22,
                    title=lambda i: ("Simulantiegolna (De Simulerade)"
                                     if i == 0 else f"{TITELORD[i]} {i}"),
                    author=lambda i: ("Simulanda Simulandersson" if i == 0
                                      else f"Upp {i}"))
    lane, post = FakeLane(svar_alla(22)), FakePost()
    monkeypatch.setenv(rp.ENV_TOKEN, "a" * 64)
    monkeypatch.setenv("AI_REK_REHEARSAL_DIR", str(tmp_path))
    lines = []
    code = rp.run_pass(ts, "https://sibbamala.test/bibliotek",
                       "https://sibbamala.test",
                       get_library=library_med_html(shelf_html(graded)),
                       lane=lane, post=post, say=lines.append)
    assert code == 2 and lane.calls == 0 and post.calls == []
    assert any("near-miss" in ln and "vägrar generation" in ln
               for ln in lines)
    assert not any("Simulantiegolna" in ln for ln in lines)


def test_near_miss_classifier_green_on_honest_distance():
    """The rebase's DoD as code: honest distance passes; the subtitle-
    tail class AND the 'del N' series-suffix class flag. This classifier
    is ONE implementation serving BOTH the runtime gate and the
    fleet-side corpus rebase (OUT/lane/n8b_rebase.py) — they cannot
    drift apart."""
    graded = [{"title": "Simulantiegolna",
               "author": "Simulanda Simulandersson", "rating": 5},
              {"title": "Exempelhyllan Norr",
               "author": "Exemplaria Exempehlsson", "rating": 5}]
    near = [{"title": "Simulantiegolna (De Simulerade)",
             "author": "Simulanda Simulandersson"},
            {"title": "Simulantiegolna del 2",
             "author": "Simulanda Simulandersson"}]
    äkta = [{"title": "Alfabetets Hus", "author": "Någon Annan"},
            {"title": "Dagdrömsängen", "author": "Henning Söder"},
            {"title": "Exemplariska Ekbräcken",
             "author": "Exempehlsson Simulanda"}]
    traff = {r["title"] for r, _ in belt.near_miss_kandidater(near, graded)}
    assert traff == {"Simulantiegolna (De Simulerade)",
                     "Simulantiegolna del 2"}
    assert belt.near_miss_kandidater(äkta, graded) == []


def test_full_never_runs_unrehearsed(tmp_path, monkeypatch):
    """DA c5 F-P4-1, the 0→1 sweep cliff: a --full POST without a
    completed dry-run rehearsal refuses FIRST — before the shelf read,
    before the lane ask, before the door (every seam proves zero
    calls)."""
    post = FakePost()
    code, lines, lane, post = kör(monkeypatch, tmp_path, full=True,
                                  rehearse=False, post=post)
    assert code == 2 and lane.calls == 0 and post.calls == []
    assert any("--full vägras" in ln and "fullbordad --dry-run" in ln
               for ln in lines)


def test_dry_run_rehearsal_authorizes_one_full_run(tmp_path, monkeypatch):
    """The authorized sequence, end to end over seams: --dry-run
    completes (stamp written), the --full in the same window POSTs the
    full-swap envelope exactly once."""
    post = FakePost()
    code, _, _, post = kör(monkeypatch, tmp_path, full=True, post=post)
    assert code == 0 and len(post.calls) == 1
    assert post.calls[0][3] is True                   # the full envelope
    stamps = list(tmp_path.glob("ai-rek-rehearsal-*.json"))
    assert len(stamps) == 1
    stamp = json.loads(stamps[0].read_text(encoding="utf-8"))
    assert stamp["accepted"] >= rp.MIN_OUTPUT_ROWS and "ts" in stamp
    assert (stamps[0].stat().st_mode & 0o777) == 0o600


def test_rehearsal_belt_rejects_stale_window_and_changed_corpus(tmp_path,
                                                                 monkeypatch):
    """The stamp is not a talisman: a rehearsal older than the window,
    and a corpus whose BYTES changed after the rehearsal, both refuse
    the --full again — the sha is the promise that the rows rehearsed
    are the rows that ride."""
    monkeypatch.setenv(rp.ENV_TOKEN, "a" * 64)
    monkeypatch.setenv("AI_REK_REHEARSAL_DIR", str(tmp_path))
    monkeypatch.setenv("AI_REK_REHEARSAL_WINDOW_S", "0")   # window closed
    ts = korpus_tsv(tmp_path / "corpus.tsv")
    biblio = "https://sibbamala.test/bibliotek"
    base = "https://sibbamala.test"
    ledd = library_med_html(shelf_html(GRADERADE))
    code = rp.run_pass(ts, biblio, base, dry_run=True, get_library=ledd,
                       lane=FakeLane(svar_alla(21)), post=FakePost(),
                       say=lambda line: None)
    assert code == 0                                   # stamp written
    lines = []
    code = rp.run_pass(ts, biblio, base, full=True, get_library=ledd,
                       lane=FakeLane(svar_alla(21)), post=FakePost(),
                       say=lines.append)
    assert code == 2 and any("äldre än fönstret" in ln for ln in lines)
    monkeypatch.delenv("AI_REK_REHEARSAL_WINDOW_S")    # window open again
    data = open(ts, encoding="utf-8").read().replace("quote 7", "quote SIJ")
    open(ts, "w", encoding="utf-8").write(data)        # corpus changed!
    lines = []
    code = rp.run_pass(ts, biblio, base, full=True, get_library=ledd,
                       lane=FakeLane(svar_alla(21)), post=FakePost(),
                       say=lines.append)
    assert code == 2 and any("annan korpus" in ln for ln in lines)


def test_plain_upsert_needs_no_rehearsal(tmp_path, monkeypatch):
    """MC 12616's default path stays byte-identical: with NO stamp
    anywhere, the plain (non-full) POST still rides — the belt covers
    --full, the sweep mode, and nothing else."""
    post = FakePost()
    code, _, _, post = kör(monkeypatch, tmp_path, post=post)
    assert code == 0 and len(post.calls) == 1
    assert post.calls[0][3] is False
