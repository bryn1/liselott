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
  door argv            the POST is curl argv on the shared transport:
                       X-Ai-Rek-Token header, --data-binary @- stdin,
                       body == the ranked JSON rows, {base}/ai-rek
  token shape          malformed AI_REC_DOOR_TOKEN => refuse before the
                       door; the VALUE never appears in any output line
ONE live-optional leg (real Lane E) is skipped unless AI_REK_LIVE=1.
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


def korpus_tsv(path, n=21, title=lambda i: f"Bok {i}",
                author=lambda i: f"Upp {i}"):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write("\t".join(rp.CORPUS_COLS) + "\n")
        for i in range(n):
            fh.write("\t".join([
                isbn(i), title(i), author(i), "2024", f"why {i}",
                f"https://rec.example/{i}", f"quote {i}", f"fit-note {i}",
                "mix", "2024 VERIFIED", "firecrawl", "xsearch:1",
                "VERIFIED"]) + "\n")
    return path


class FakeLane:
    """Answer carrier; .prompt captures what the model was actually asked."""

    def __init__(self, text):
        self.text, self.calls, self.prompt = text, 0, None

    def __call__(self, prompt):
        self.calls += 1
        self.prompt = prompt
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

    def __call__(self, url, token, rows):
        self.calls.append((url, token, rows))
        return self.status, self.body


def library_med_html(html):
    return lambda url: (pp.read_graded(html), None)


GRADERADE = [{"title": "En helt annan bok", "author": "Annat Namn",
              "rating": 5}]


def kör(mp, tmp_path, *, n=21, graded=GRADERADE, lane_text=None, post=None,
        dry=False, token="a" * 64):
    """One full run over faked seams; `mp` owns the token env (the delivery
    legs ride a VALID 64-hex token unless a leg names its own)."""
    mp.setenv(rp.ENV_TOKEN, token)
    ts = korpus_tsv(tmp_path / "corpus.tsv", n=n)
    lane = FakeLane(lane_text if lane_text is not None else svar_alla(n))
    post = post or FakePost()
    lines = []
    code = rp.run_pass(ts, "https://sibbamala.test/liselott/bibliotek",
                       "https://sibbamala.test/liselott",
                       dry_run=dry,
                       get_library=library_med_html(shelf_html(graded)),
                       lane=lane, post=post, say=lines.append)
    return code, lines, lane, post


# --- the legs ----------------------------------------------------------------

def test_join_drops_owned_books(tmp_path, monkeypatch):
    """The corpus book the shelf grades — spelled DIFFERENTLY, identity is
    the wish_key normalization, not string equality — never reaches the
    prompt, and never rides the POST."""
    graded = [{"title": "BOK 0", "author": "upp 0", "rating": 4}]
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


def test_door_post_rides_shared_curl_argv(tmp_path, monkeypatch):
    """The delivery argv shape ONE LEVEL BELOW the transport (the pris_vakt
    FakeCurl posture): curl argv list, never a shell — X-Ai-Rek-Token on
    the header, --data-binary @- on stdin, {base}/ai-rek last, the body IS
    the ranked rows and kategori rides every one of them (MC 12602
    F-P4-1)."""
    from types import SimpleNamespace
    from scripts import curl_transport as ct
    anrop = []

    class FakeCurl:
        """subprocess.run replaced wholesale; the --output file gets the
        canned door receipt — the real _curl runs above it."""

        def __call__(self, argv, **kw):
            anrop.append((argv, kw))
            with open(argv[argv.index("--output") + 1], "wb") as fh:
                fh.write(b'{"inserted": 21}')
            return SimpleNamespace(returncode=0, stdout=b"200", stderr=b"")
    monkeypatch.setattr(ct.subprocess, "run", FakeCurl())
    monkeypatch.setenv(rp.ENV_TOKEN, "a" * 64)
    lines = []
    code = rp.run_pass(korpus_tsv(tmp_path / "corpus.tsv"),
                       "https://sibbamala.test/bibliotek",
                       "https://sibbamala.test",
                       get_library=library_med_html(shelf_html(GRADERADE)),
                       lane=FakeLane(svar_alla(21)), say=lines.append)
    assert code == 0 and len(anrop) == 1
    argv, kw = anrop[0]
    assert argv[0] == "curl" and argv[-1] == "https://sibbamala.test/ai-rek"
    assert "X-Ai-Rek-Token: " + "a" * 64 in argv
    assert argv[argv.index("--data-binary") + 1] == "@-"
    assert argv[argv.index("--max-time") + 1] == str(rp.POST_TIMEOUT_S)
    assert kw["timeout"] == rp.POST_TIMEOUT_S + ct.WATCHDOG_GRACE_S
    rows = json.loads(kw["input"])
    assert len(rows) == 21
    assert all(r["kategori"] in rp.ai_rek.KATEGORIER for r in rows)


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
