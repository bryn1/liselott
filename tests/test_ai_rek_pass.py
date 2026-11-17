"""MC 12601 (M11-N5R) — the ai_rek_pass runner legs, OFFLINE (seams faked
end-to-end: library bytes / lane answer / door POST; zero network — the
socket-guard leg proves it). The parser legs for the graded shelf live in
tests/test_pris_parse.py. Planted-red per gate (one mutant at a time,
sha-verified restore) is mapped in the commit body.

  join-drops-owned     a corpus book the shelf already grades (matched
                       through wish_key — different spelling, same identity)
                       never reaches the prompt or the POST
  hallucination        a lane answer naming an isbn outside the loaded
                       corpus is REJECTED in code (carry N3), never POSTed
  hostile JSON         prose / dict-not-list / markdown fence / truncated
                       garbage => refused, exit 3, ZERO door calls
  fit domain           bool / non-finite / outside [0,1] => row REJECTED
                       (refused, never clamped — app/ai_rek._obs parity);
                       the valid neighbours ride on and fill the floor
  dry-run zero network socket.socket/create_connection/getaddrinfo patched
                       to raise; a dry run exits 0, prints rows, POSTS
                       NOTHING
  taste-profile-empty  shelf answers with zero graded cards => refuse
                       BEFORE the lane ask (MC 12602 scope row 2)
  twin dedupe          two corpus rows that are ONE book (same wish_key
                       identity, different isbn) => the best-ranked rides
                       the POST, the twin is dropped (carry N1)
  control chars        \\x1f in a corpus field => the corpus is refused at
                       load (N5); a lane reason smuggled with \\x00 is
                       stopped by the payload-side belt
  N3 merge input       one isbn repeated across two corpus books => corpus
                       refused (the merge lane never runs on its input)
  floor                accepted rows < MIN_OUTPUT_ROWS => exit 4, ZERO POSTs
  door argv            the delivery-shape weld MOVED to
                       tests/test_door_transport.py at MC 12616 (config
                       transport, ZERO token bytes in argv, live /proc
                       leg) — one concern per file under the 600-line
                       test ceiling; the fixtures here are imported there
  full mode            --full / run_pass(full=True) rides the door's
                       generation envelope, DEFAULT off (MC 12616)
  lane timeout         lane_ask budget: default 600 s (the shipped 300
                       died mid-generation, DA c4 P3), --lane-timeout
                       threaded through main
  token shape          malformed AI_REC_DOOR_TOKEN => refuse before the
                       door; the VALUE never appears in any output line
  mix gate             nyhet-only refuses (exit 6), klassiker-only refuses
                       (exit 6), a mixed generation rides (owner scope:
                       "newly released books as well as classics", DA c3)
  owned-named-back     an isbn naming a JOIN-DROPPED owned corpus row is
                       refused post-parse (belt F-C3-1, the tester's L11)
ONE live-optional leg (real Lane E) is skipped unless AI_REK_LIVE=1.
NOTE on the fixture titles (MC 12617): the corpus fixture rows now carry
DISTINCT Swedish-looking titles (TITELORD — pairwise near-miss-clean by
computation). In the old dense "Bok N" space every pair of synthetic
titles is one edit apart, which the near-miss gate correctly reads as an
ownership ambiguity; the leg INTENTS are unchanged, the dense fixture
space simply moved outside the gate's real-world semantics.
"""
import json
import os
import re
import socket

import pytest

from scripts import ai_rek_pass as rp
from scripts import pris_parse as pp


# --- fixtures: the shelf markup and the corpus.tsv shape ----------------------

def shelf_html(cards):
    """The app's OWN card markup (_bokkort.html), graded or not — parsed by
    the REAL pp.read_graded, never by a hand-rolled fake parser."""
    ut = ['<html><body><ul class="hylla">']
    for n, c in enumerate(cards):
        ut.append('<li class="bok-kort"><a class="bok-lank" '
                  f'href="/liselott/bok/{n + 1}"><img class="omslag" '
                  f'alt="x" src="/c"><span class="titel">{c["title"]}</span>'
                  f'</a><p class="forfattare">{c.get("author", "")}</p>')
        if c.get("rating"):
            ut.append(f'<span class="stjarnor" role="img" aria-label="Betyg '
                      f'{c["rating"]} av 5"><span aria-hidden="true">'
                      f'{"*" * c["rating"]}</span></span>')
        ut.append("</li>")
    ut.append("</ul></body></html>")
    return "".join(ut)


def isbn(i):
    """The synthetic corpus isbn lane: 13 ASCII digits, unique per i. The
    9999 prefix is NO valid ISBN group (the exposure gate caught the first
    lane on a real-book collision) — this lane can never name a real
    book."""
    return f"9999100{i:06d}"


KATERS = ("new_release", "classic", "mix")

# MC 12617: fixture titles ride DISTINCT real-looking Swedish names — the
# near-miss gate (ai_rek_belt) reads the old dense "Bok N" space as one big
# ownership ambiguity. Pairwise near-miss-clean VERIFIED by computation
# (folded ratio < 0.62 and no token containment, all 24×23 ordered pairs,
# plus every title vs GRADERADE).
TITELORD = [
    "Alfabetets Hus", "Barnvagnsbron", "Cykelverkstaden Norr", "Dagdrömsängen",
    "Ekbackens Tavla", "Fyrhornets Skugga", "Glasögonbindeln",
    "Hammarbyns Krog", "Infallsvinkeln Idag", "Journalistens Nyckel",
    "Karusellen Imorgon", "Lantvägens Krämeri", "Musiksalongens Hemlighet",
    "Naturreservatet Söder", "Orkesterdiket", "Pandemin Papper",
    "Resväskebudet", "Skördemånens Fågel", "Trädgårdsmästarens Arv",
    "Upprorets Utsikt", "Vintergatans Vaktare", "Yrkesvalets Ångest",
    "Ångertågets Signal", "Öppet Hus För Alla"]


def korpus_tsv(path, n=21, title=lambda i: f"{TITELORD[i % 24]} {i}",
                author=lambda i: f"Upp {i}",
                category=lambda i: KATERS[i % 3]):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write("\t".join(rp.CORPUS_COLS) + "\n")
        for i in range(n):
            fh.write("\t".join([
                isbn(i), title(i), author(i), "2024", f"why {i}",
                f"https://rec.example/{i}", f"quote {i}", f"fit-note {i}",
                category(i), "2024 VERIFIED", "firecrawl", "xsearch:1",
                "VERIFIED"]) + "\n")
    return path


class FakeLane:
    """Answer carrier; .prompt captures what the model was actually asked
    (joined across turns — substring legs stay substring legs), .turer the
    RAW (system, user) pair from MC 12617's split (None on a legacy str)."""

    def __init__(self, text):
        self.text, self.calls, self.prompt, self.turer = text, 0, None, None

    def __call__(self, prompt):
        self.calls += 1
        self.turer = None if isinstance(prompt, str) else prompt
        self.prompt = (prompt if isinstance(prompt, str)
                       else "\n\n".join(prompt))
        return self.text


def svar(isbns):
    return json.dumps([{"isbn13": i, "fit": 0.9 - k / 100,
                        "reason": "Passar smakprofilen enligt betygen."}
                       for k, i in enumerate(isbns)])


def svar_alla(n, fran=0):
    return svar([isbn(i) for i in range(fran, n)])


class FakePost:
    def __init__(self, status=200, body=b'{"inserted": 21}'):
        self.status, self.body, self.calls = status, body, []

    def __call__(self, url, token, rows, *, full=False):
        self.calls.append((url, token, rows, full))
        return self.status, self.body


def library_med_html(html):
    return lambda url: (pp.read_graded(html), None)


GRADERADE = [{"title": "En helt annan bok", "author": "Annat Namn",
              "rating": 5}]


def kör(mp, tmp_path, *, n=21, graded=GRADERADE, lane_text=None, post=None,
        dry=False, token="a" * 64, category=lambda i: KATERS[i % 3],
        full=False, rehearse=True):
    """One full run over faked seams; `mp` owns the token env (the delivery
    legs ride a VALID 64-hex token unless a leg names its own). MC 12617:
    the rehearsal stamp dir is per-leg tmp (no /tmp litter, no cross-leg
    bleed), and a `full=True` run is REHEARSED FIRST by a plain dry-run on
    the same corpus/library — pass `rehearse=False` to attack the belt."""
    mp.setenv(rp.ENV_TOKEN, token)
    mp.setenv("AI_REK_REHEARSAL_DIR", str(tmp_path))
    ts = korpus_tsv(tmp_path / "corpus.tsv", n=n, category=category)
    lane = FakeLane(lane_text if lane_text is not None else svar_alla(n))
    post = post or FakePost()
    lines = []
    if full and rehearse:
        rr = rp.run_pass(ts, "https://sibbamala.test/liselott/bibliotek",
                         "https://sibbamala.test/liselott", dry_run=True,
                         get_library=library_med_html(shelf_html(graded)),
                         lane=FakeLane(lane.text), post=FakePost(),
                         say=lambda line: None)
        assert rr == 0, "rehearsal must pass before the --full leg runs"
    code = rp.run_pass(ts, "https://sibbamala.test/liselott/bibliotek",
                       "https://sibbamala.test/liselott",
                       dry_run=dry,
                       get_library=library_med_html(shelf_html(graded)),
                       lane=lane, post=post, say=lines.append, full=full)
    return code, lines, lane, post


# --- the legs ----------------------------------------------------------------

def test_join_drops_owned_books(tmp_path, monkeypatch):
    """The corpus book the shelf grades — spelled DIFFERENTLY, identity is
    the wish_key normalization, not string equality — never reaches the
    prompt, and never rides the POST."""
    graded = [{"title": "ALFABETETS HUS 0", "author": "upp 0", "rating": 4}]
    post = FakePost()
    code, lines, lane, post = kör(
        monkeypatch, tmp_path, graded=graded, n=22, post=post,
        lane_text=svar([isbn(i) for i in range(1, 22)]))
    assert code == 0 and len(post.calls) == 1
    assert isbn(0) not in lane.prompt                  # never offered to the model
    assert isbn(0) not in [r["isbn13"] for r in post.calls[0][2]]
    assert any("drogs_bort=1" in ln for ln in lines)


def test_hallucinated_isbn_rejected(tmp_path, monkeypatch):
    """An answer naming an isbn the corpus does not carry is rejected IN
    CODE (carry N3: every POSTed isbn exists in the corpus.tsv rows) —
    named in the log, never in the payload; the real rows ride on."""
    post = FakePost()
    rankade = json.loads(svar_alla(22))                # 22 äkta...
    rankade.append({"isbn13": "9999999999999", "fit": 0.99,
                    "reason": "Bok som inte finns i corpus."})  # ...plus en fe
    code, lines, _, post = kör(monkeypatch, tmp_path, n=22,
                               lane_text=json.dumps(rankade), post=post)
    assert code == 0
    assert any("9999999999999" in ln and "finns inte i corpus" in ln
               for ln in lines)
    posted = [r["isbn13"] for r in post.calls[0][2]]
    assert "9999999999999" not in posted and len(posted) == 22


@pytest.mark.parametrize("hostile", [
    "Jag kan inte rekommendera böcker, tyvärr.",            # prose, no JSON
    '{"isbn13": "9999100000000", "fit": 0.9}',             # object, not array
    '```json\n[{"isbn13": "9999100000000", "fit": 0.9,'
    ' "reason": "bra"}]\n```',                             # markdown fence
    '[{"isbn13": "9999100000000", "fit": 0.9, "reason": "x"},',   # truncated
    '[{"isbn13": "9999100000000" xss}, {}]',                     # corrupt
])
def test_hostile_llm_json_refused(tmp_path, monkeypatch, hostile):
    """Strict parse: the answer must BE the array — no prose scraping, no
    fence salvage => exit 3, ZERO door calls."""
    post = FakePost()
    code, lines, _, _ = kör(monkeypatch, tmp_path, lane_text=hostile,
                       post=post)
    assert code == 3 and post.calls == []
    assert any("lane-svar avvisas" in ln for ln in lines)


def test_fit_refused_outside_unit_interval(tmp_path, monkeypatch):
    """The fit domain, app/ai_rek._obs's posture: bool / above 1 / below 0
    / non-finite rows are REFUSED (never clamped — a clamp would forge a
    score the model never gave); the valid rows fill the floor and ride."""
    rankade = json.loads(svar_alla(24))
    for i, bad in enumerate([True, 1.4, -0.01, float("nan")]):
        rankade[i]["fit"] = bad
    post = FakePost()
    code, lines, _, post = kör(monkeypatch, tmp_path, n=24,
                               lane_text=json.dumps(rankade), post=post)
    assert code == 0
    assert sum(1 for ln in lines if "utanför" in ln) == 4
    rows = post.calls[0][2]
    assert len(rows) == 20
    assert all(isinstance(r["fit"], float) and 0.0 <= r["fit"] <= 1.0
               for r in rows)


def test_dry_run_makes_zero_network_calls(tmp_path, monkeypatch):
    """The socket-prove leg: every Python network primitive raises; the dry
    run completes on seams, prints the ranked rows, POSTS NOTHING."""
    def boomer(*a, **k):
        raise AssertionError("nätverk i en socket-guardad leg")
    for name in ("socket", "create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, name, boomer)
    post = FakePost()
    code, lines, lane, _ = kör(monkeypatch, tmp_path, dry=True, post=post)
    assert code == 0 and post.calls == [] and lane.calls == 1
    assert any(ln.startswith("DRY-RUN: ") and "INGET POSTAT" in ln
               for ln in lines)
    rader = json.loads(next(ln for ln in lines
                            if ln.startswith("DRY-RUN-RADER ")
                            ).split(" ", 1)[1])
    assert len(rader) == 21 and rader[0]["fit"] >= rader[-1]["fit"]


def test_taste_profile_empty_refusal(tmp_path, monkeypatch):
    """The shelf answers with ZERO graded cards => refuse BEFORE the lane
    ask (MC 12602 scope row 2: no 'baserat på hyllan' without a hylla)."""
    post = FakePost()
    code, lines, lane, post = kör(monkeypatch, tmp_path, graded=[], post=post)
    assert code == 2 and lane.calls == 0 and post.calls == []
    assert any("smakprofil tom" in ln and "vägrar POST" in ln for ln in lines)


def test_twin_pair_deduped_by_identity(tmp_path, monkeypatch):
    monkeypatch.setenv(rp.ENV_TOKEN, "a" * 64)
    """Carry N1: two corpus rows that are ONE book (same wish_key identity,
    different isbn) — the best-ranked rides the POST, the twin is dropped;
    the door never sees two rec_keys for one book."""
    ts = korpus_tsv(tmp_path / "corpus.tsv", n=22,
                    title=lambda i: "Samma Bok" if i in (0, 1) else f"Bok {i}",
                    author=lambda i: "Författare" if i in (0, 1)
                    else f"Upp {i}")
    rankade = json.loads(svar_alla(22))
    rankade[1]["fit"] = 0.05                           # twinen sist i rank
    lane = FakeLane(json.dumps(rankade))
    post = FakePost()
    lines = []
    code = rp.run_pass(ts, "https://sibbamala.test/bibliotek",
                       "https://sibbamala.test",
                       get_library=library_med_html(shelf_html(GRADERADE)),
                       lane=lane, post=post, say=lines.append)
    assert code == 0
    rows = post.calls[0][2]
    isbns = [r["isbn13"] for r in rows]
    assert isbn(0) in isbns and isbn(1) not in isbns
    assert any("DUBLETT" in ln for ln in lines)
    assert len(rows) == 21                             # 22 kandidater, ett par


def test_control_chars_refused(tmp_path, monkeypatch):
    """N5 on both sides: a corpus field carrying \\x1f kills the corpus AT
    LOAD (the join-injection door never opens); a lane reason smuggled with
    \\x00 is stopped by the payload-side belt."""
    ts = korpus_tsv(tmp_path / "bad.tsv")
    data = open(ts, encoding="utf-8").read().replace("Upp 3", "Upp\x1f3")
    open(ts, "w", encoding="utf-8").write(data)
    lines = []
    code = rp.run_pass(ts, "x", "y",
                       get_library=library_med_html(shelf_html(GRADERADE)),
                       lane=FakeLane(svar_alla(21)),
                       post=FakePost(), say=lines.append)
    assert code == 2
    assert any("korpus avvisad" in ln and "N5" in ln for ln in lines)
    rankade = json.loads(svar_alla(21))
    rankade[0]["reason"] = "utmärkt \u0000 bok"
    post = FakePost()
    code2, lines2, _, post = kör(monkeypatch, tmp_path, n=21,
                                 lane_text=json.dumps(rankade), post=post)
    assert code2 == 0 and len(post.calls[0][2]) == 20
    assert any("kontrolltecken i reason" in ln for ln in lines2)


def test_duplicate_isbn_across_books_refused(tmp_path):
    """N3 at the input: one isbn carried by TWO corpus books is the
    isbn-merge trap — the corpus that carries it is refused before
    anything is asked of the lane."""
    ts = korpus_tsv(tmp_path / "dup.tsv",
                    title=lambda i: "Samma Bok" if i else f"Bok {i}")
    rader = open(ts, encoding="utf-8").read().splitlines()
    rader[2] = rader[2].replace(isbn(1), isbn(0))
    open(ts, "w", encoding="utf-8").write("\n".join(rader) + "\n")
    lines = []
    code = rp.run_pass(ts, "x", "y",
                       get_library=library_med_html(shelf_html(GRADERADE)),
                       lane=FakeLane(svar_alla(21)),
                       post=FakePost(), say=lines.append)
    assert code == 2
    assert any("dupliceras" in ln for ln in lines)


def test_floor_thin_generation(tmp_path, monkeypatch):
    """Accepted rows < MIN_OUTPUT_ROWS => exit 4, loud, ZERO POSTs: a thin
    generation is a failed generation, never a small delivery."""
    post = FakePost()
    code, lines, _, _ = kör(monkeypatch, tmp_path, n=21,
                            lane_text=svar([isbn(i) for i in range(15)]),
                            post=post)
    assert code == 4 and post.calls == []
    assert any("för tunn generation" in ln for ln in lines)


def test_token_shape_guarded_never_echoed(tmp_path, monkeypatch):
    """A malformed AI_REC_DOOR_TOKEN => refuse BEFORE the door (the 64-hex
    shape is the door's own), and the secret VALUE never lands in any
    output line."""
    hemligt = "NOT-A-64-HEX-DOOR-TOKEN-VARDE"
    post = FakePost()
    code, lines, _, _ = kör(monkeypatch, tmp_path, post=post, token=hemligt)
    assert code == 2 and post.calls == []
    assert any("fel form" in ln for ln in lines)
    assert not any(hemligt in ln for ln in lines)


def test_mix_gate_refuses_nyhet_only(tmp_path, monkeypatch):
    """Owner scope ("newly released books as well as classics", DA c3 item
    2): an output carrying only nyhet is NOT the promised generation =>
    refuse, exit 6, ZERO POSTs."""
    post = FakePost()
    code, lines, _, _ = kör(monkeypatch, tmp_path, post=post,
                            category=lambda i: "new_release")
    assert code == 6 and post.calls == []
    assert any("blandningsvillkor" in ln and "klassiker" in ln
               for ln in lines)


def test_mix_gate_refuses_klassiker_only(tmp_path, monkeypatch):
    """The mirror leg: klassiker-only output refuses too — the gate checks
    BOTH halves, not one + default."""
    post = FakePost()
    code, lines, _, _ = kör(monkeypatch, tmp_path, post=post,
                            category=lambda i: "classic")
    assert code == 6 and post.calls == []
    assert any("blandningsvillkor" in ln and "nyhet" in ln for ln in lines)


def test_mix_gate_mixed_rides(tmp_path, monkeypatch):
    """Both halves present => the generation rides the door unchanged."""
    post = FakePost()
    code, _, _, post = kör(monkeypatch, tmp_path, post=post)
    assert code == 0 and len(post.calls) == 1
    kats = {r["kategori"] for r in post.calls[0][2]}
    assert {"nyhet", "klassiker"} <= kats


def test_full_flag_defaults_off_and_rides_the_seam(tmp_path, monkeypatch):
    """MC 12616: the runner's generation mode is EXPLICIT opt-in — the
    default POST rides the seam with full=False (plain array, today's
    mode), --full/full=True rides the SAME seam with full=True; identical
    rows either way, only the mode differs."""
    post = FakePost()
    code, _, _, post = kör(monkeypatch, tmp_path, post=post)
    assert code == 0 and post.calls[0][3] is False
    post2 = FakePost()
    code, _, _, post2 = kör(monkeypatch, tmp_path, post=post2, full=True)
    assert code == 0 and post2.calls[0][3] is True
    assert [r["isbn13"] for r in post.calls[0][2]] == \
        [r["isbn13"] for r in post2.calls[0][2]]      # same rows, mode only


def test_main_parses_full_defaulting_off(monkeypatch):
    """CLI face of the opt-in: no flag ⇒ full=False, `--full` ⇒ True,
    threaded into run_pass by main and by nothing else."""
    anrop = {}

    def fake_run_pass(corpus, library, base, **kw):
        anrop.update(kw)
        return 0

    monkeypatch.setattr(rp, "run_pass", fake_run_pass)
    assert rp.main(["--corpus", "c.tsv"]) == 0
    assert anrop["full"] is False
    assert rp.main(["--corpus", "c.tsv", "--full"]) == 0
    assert anrop["full"] is True


def test_owned_book_named_back_is_refused(tmp_path, monkeypatch):
    """F-C3-1 (the tester's L11): the model names back the isbn of a corpus
    row the JOIN dropped as owned — post-parse the belt refuses it even
    though the row exists in corpus.tsv; the offered set is the accepted
    set. All other rows ride."""
    graded = [{"title": "Alfabetets Hus 0", "author": "Upp 0", "rating": 4}]
    post = FakePost()
    code, lines, _, post = kör(
        monkeypatch, tmp_path, graded=graded, n=22, post=post,
        lane_text=svar([isbn(i) for i in range(22)]))   # ägda raden med!
    assert code == 0
    assert any(isbn(0) in ln and "F-C3-1" in ln for ln in lines)
    posted = [r["isbn13"] for r in post.calls[0][2]]
    assert isbn(0) not in posted and len(posted) == 21


def test_lane_timeout_defaults_600_and_flag_threads_through(monkeypatch):
    """MC 12616 bonus (DA c4 P3): the 300 s shipped budget died mid-
    generation on the live DA run — lane_ask's timeout now DEFAULTS to 600
    s and main's `--lane-timeout` moves it, threaded through the lane
    seam. urllib is faked: the legs read WHICH timeout was asked for."""
    import urllib.request

    class Svar:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"choices": [{"message":
                                            {"content": "[]"}}]}).encode()

    tidsgranser = []

    def fake_urlopen(req, timeout=None):
        tidsgranser.append(timeout)
        return Svar()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert rp.lane_ask("x") == "[]"
    assert tidsgranser == [rp.LANE_TIMEOUT_S] == [600]
    assert rp.lane_ask("x", timeout_s=42) == "[]"
    assert tidsgranser[-1] == 42
    anrop = {}

    def fake_run_pass(corpus, library, base, **kw):
        anrop.update(kw)
        return 0

    monkeypatch.setattr(rp, "run_pass", fake_run_pass)
    assert rp.main(["--corpus", "c.tsv"]) == 0
    assert anrop["lane"]("prompt") == "[]"
    assert tidsgranser[-1] == 600                      # default threads too
    assert rp.main(["--corpus", "c.tsv", "--lane-timeout", "77"]) == 0
    assert anrop["lane"]("prompt") == "[]"
    assert tidsgranser[-1] == 77                      # the flag threads too


@pytest.mark.skipif(os.environ.get("AI_REK_LIVE") != "1",
                    reason="live Lane E leg: run with AI_REK_LIVE=1")
def test_live_lane_e_ranks_real_shapes():
    """ONE live-optional leg (skipped by default): a REAL Lane E ask over
    real-shaped rows must strict-parse and stay inside the offered corpus."""
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        ts = korpus_tsv(Path(d) / "corpus.tsv", n=2)
        graded = [{"title": "Stolthet och fördom", "author": "Jane Austen",
                   "rating": 5}]
        rows, fel = rp.read_corpus(ts)
        assert fel is None
        rankade = rp.parse_ranking(rp.lane_ask(rp.build_prompt(graded, rows)))
        assert len(rankade) >= 2
        assert all(re.fullmatch(r"\d{13}", str(r["isbn13"])) for r in rankade)

