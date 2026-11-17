#!/usr/bin/env python3
# 505 lines > 400 (MC 12601 c3 fix-wave, MC 12616 on top): the WHOLE generation contract —
# corpus shape, the join, the ONE lane envelope, every code gate and the
# door delivery — is one unchecked-nothing-can-pass chain; splitting it
# scatters the single guarantee ("between corpus.tsv and the door there is
# exactly one path") across files, which is the failure mode the gate list
# in the docstring exists to prevent (coding-discipline header reason).
"""MC 12601 (M11-N5R) — the generation runner for "AI rekommenderar".

Runs FLEET-side (VM350), never inside the app: it reads the PUBLIC shelf
HTML, joins the fleet corpus against it, asks Lane E to rank + reason, and
POSTs /ai-rek through the door. NO DB access, ever — the shelf's own public
bytes are the library (the card pins it).

Inputs:
  --library  the public shelf https://sibbamala.com/liselott/bibliotek
             (scripts/curl_transport — the measured CF fact: urllib is 403'd
             at that edge, curl passes; 221 graded cards are public per
             owner scope; scripts/pris_parse.read_graded parses
             title/author/rating off the app's own _bokkort.html markup)
  --corpus   the fleet corpus TSV (26 rows, tab, 13 cols — the N1 output
             .audits/202611161817-aae834ce-n1/out/corpus.tsv)

Join (vs library): corpus rows whose BOOK the shelf already grades are
DROPPED — she is never recommended a book she has read and rated. Identity
is the app's OWN normalization, imported read-only: `onska.wish_key` (the
§5.3 seed.book_key chain) on title+author, plus the isbn13 lane when both
sides carry one (the shelf card markup carries no isbn, so the wish_key
lane is what bites today — one identity mechanism, the door's twin).

The ask (Lane E http://192.168.5.223:8888/v1/chat/completions): the ONE
compiled-default envelope idiom of scripts/cover_pass.py — one model id,
temperature 0, reasoning_effort low on both layers. Lane E is LAN-side
(no CF edge), so urllib rides there exactly as cover_pass's vision leg
does; NO new mechanism beside it. The prompt carries her GRADED taste
profile (every graded card + rating) and the corpus rows, and states that
fit must be justified BY the profile; the model may ONLY rank + reason over
the corpus rows it is handed.

Gates BEFORE a byte reaches the door (all in code, none in the prompt):
  hallucination  a returned isbn13 absent from the loaded corpus => row
                 REJECTED (`_validera` — the citation for carry N3: every
                 POSTed isbn exists in the corpus.tsv rows).
  fit            non-finite / bool / outside [0,1] => row REJECTED.
                 READING used: REFUSE, never clamp — app/ai_rek._obs
                 shape-rejects the same values, and a silent clamp would
                 forge a score the model never gave.
  identity       dedupe by isbn UNION wish_key-normalized title+author
                 BEFORE POST (carry N1): one identity per generation,
                 never two rows whose rec_keys differ for one book.
  control chars  every POSTed string is asserted free of C0/C1 control
                 characters (carry N5: \x1f is seed.book_key's join
                 delimiter — one control char in a field is door-reachable
                 join injection; the corpus is asserted at load too, and a
                 corpus that repeats one isbn between two books is refused
                 at load — the N3 merge lane can never run on its input).
  kategori       nyhet|klassiker|blandad rides EVERY row (MC 12602
                 F-P4-1's column); the corpus `category` maps
                 classic/new_release/mix onto the door's vocabulary — the
                 mix the card says is already in the corpus.
  floor          fewer than MIN_OUTPUT_ROWS accepted rows => REFUSE the
                 POST, loud, non-zero: a thin generation is a failed one.
  mix            the accepted output carries <1 nyhet OR <1 klassiker =>
                 REFUSE, loud, non-zero, ZERO POSTs (owner scope, the
                 owner's own task words: "newly released books as well as
                 classics" — a generation that answers only one half of
                 that promise is not the promised generation; DA c3 FIX
                 item 2). blandad rows are welcome, never load-bearing.
  taste          zero graded rows from --library => REFUSE, loud, non-zero,
                 BEFORE the lane ask (MC 12602 scope row 2: "based on the
                 current graded library" must be real).

Delivery: POST {base}/ai-rek through curl_transport (ONE transport for
both door runners — this card's shared extraction). The credential from
env AI_REC_DOOR_TOKEN rides the `X-Ai-Rek-Token` header through curl's
PLAIN `--config <per-call 0600 tmpfile>` form (MC 12616, DA c3 P2 — the
reproduced /proc/<curl>/cmdline leak: ZERO token bytes on the child's
argv, leg-proved against a live curl child; DA c6 F-P1-1: NOT the `@`
form — curl silently ignores it and the header never arrives, the
real-wire delivery legs in tests/test_door_transport.py hold arrival),
64-hex asserted through the door's OWN
TOKEN_SHAPE, the value never echoed. --dry-run prints the ranked JSON and
POSTS NOTHING (the door POST is the ONLY thing dry-run skips — the shelf
read and the lane ask still run, else the demo would prove nothing).
--full (DEFAULT off, MC 12616) sends the door's full-swap envelope: the
POSTed list then IS the complete new generation and the door deletes the
state='new' rows absent from it (server-side sweep, deleted_n in the
receipt); --lane-timeout (default 600 s, DA c4 P3) sizes the lane ask —
the 300 s it shipped with died mid-generation on the live DA run.

KNOWN LIMITS, documented not papered over:
  FULL-REPLACEMENT SWEEP (MC 12602 scope row 1) — CLOSED by MC 12616: the
  door now takes the optional full-swap envelope `{"generation": rows}`
  and this runner's `--full` flag (DEFAULT off — explicit opt-in) sends
  it. Rows still `new` that are ABSENT from this generation's output are
  deleted door-side (state accept/decline are NEVER deleted; empty
  generation is refused fail-loud, rows kept); the answer gains
  deleted_n. The default upsert path (no `--full`) is byte-identical to
  MC 12601, so the shipped mode keeps working unchanged.
  DECLINE-FLIP RACE (carry N2, app-side P3): unreachable from this runner
  lane — the runner is the single writer; the race needs the owner's
  browser flip landing mid-ingest, which is app-side.
  OWNED-BOOK TITLE SPELLINGS (measured on the live demo 2026-11-17, the
  claim corrected by DA c3 F-P2-2c): the corpus ships some titles with a
  subtitle tail while the shelf grades the plain title — wish_key cannot
  unify the two spellings, so one already-graded book was offered (the
  lane's own reason even cited her rating for it). RETIRED HERE: the earlier
  sentence pointing at the alias table as the repair was DEAD for this
  class — seed.book_key alias-resolves AUTHOR names only, titel is never
  looked up (DA probe3), so no alias row can ever repair a TITLE misspelling
  (and the table is NOT empty — 15 off-repo entries; the "empty on this
  host" claim was also false). The repair that WORKS is data-side: the
  shelf-exact corpus rebase (MC 12617). This runner deliberately adds NO
  second title normalizer beside the §5.3 chain. (The diary's own strings
  are named nowhere here: the exposure gate counts this file.)
"""
import argparse
import csv
import json
import math
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import ai_rek, onska                # THE door's vocabulary + identity
from scripts import pris_parse as pp         # THE shelf-page parser
from scripts.curl_transport import _curl, _curl_config   # THE shared transport

ENV_URL, ENV_TOKEN = "LISELOTT_URL", ai_rek.AI_REK_TOKEN_ENV
BASE_DEFAULT = "https://sibbamala.com/liselott"
GET_TIMEOUT_S, POST_TIMEOUT_S = 15, 30
LANE_TIMEOUT_S = 600            # MC 12616 (DA c4 P3): the shipped 300 s
#                                 died mid-generation on the live DA run;
#                                 --lane-timeout moves this default
TOKEN_SHAPE = ai_rek.TOKEN_SHAPE            # the door's 64-hex shape, ONE shape
LANE_URL = os.environ.get("AI_REK_LANE_URL",
                          "http://192.168.5.223:8888/v1/chat/completions")
LANE_MODEL = os.environ.get("AI_REK_LANE_MODEL", "qwen3.8-flash-next")
LANE_MAX_TOKENS = 12000                     # measured 2026-11-16: 6000
#                                 died reasoning-truncation on the
#                                 221-card profile x 25 rows (empty
#                                 content, gate refused it); 12000 is
#                                 answer + reasoning headroom
MIN_OUTPUT_ROWS = 20                        # MC 12601: output >=20 ranked rows

# The corpus.tsv's 13 columns, exactly as the N1 output ships them.
CORPUS_COLS = ["isbn13", "title", "author", "year", "why", "review_source_url",
               "review_quote", "fit_note", "category", "year_basis",
               "fetch_method", "libris_id", "citation_status"]
# The corpus' category vocabulary mapped onto the door's CHECK vocabulary
# (app.ai_rek.KATEGORIER) — one mapping, the door's values on the far side.
KATEGORI_MAP = {"new_release": "nyhet", "classic": "klassiker", "mix": "blandad"}

ISBN_FULL = re.compile(r"\d{13}")


def _har_kontrolltecken(text):
    """True when a string carries a C0/C1 control char (\\x1f included):
    `seed.book_key` joins authors on \\x1f and the door re-keys through it,
    so ONE control char in a POSTed field is a door-reachable join
    injection (MC 12602 carry N5)."""
    return any(unicodedata.category(c) == "Cc" for c in text)


def read_corpus(path):
    """corpus.tsv -> (rows, None) or (None, reason). The parse pins the
    shipped shape: header == CORPUS_COLS exactly, tab rows of 13 fields;
    isbn13 exactly 13 ASCII digits and UNIQUE across rows (two books
    sharing one isbn is the N3 merge-lane trap — the corpus that carries it
    is refused here, the furthest point from the door); year empty or an
    int in the door's 1000..2100; NO field carries a control char (N5);
    title/review_source_url non-empty (the door's shape duty, asked at
    load). Every kept row carries its door values: kategori + wish_key."""
    rows, isbns = [], {}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh, delimiter="\t")
        header = next(reader, None)
        if header != CORPUS_COLS:
            return None, "kolumnrubriker matchar inte corpus.tsv:s 13 kolumner"
        for n, f in enumerate(reader, start=2):
            if len(f) != len(CORPUS_COLS):
                return None, f"rad {n}: {len(f)} fält, förväntades 13"
            row = dict(zip(CORPUS_COLS, (x.strip() for x in f)))
            bad = [k for k, v in row.items() if _har_kontrolltecken(v)]
            if bad:
                return None, f"rad {n}: kontrolltecken i {','.join(bad)} (N5)"
            isbn = row["isbn13"]
            if not (ISBN_FULL.fullmatch(isbn) and isbn.isascii()):
                return None, f"rad {n}: isbn13 inte 13 ASCII-siffror"
            if isbn in isbns:
                return None, f"rad {n}: isbn13 dupliceras över två böcker (N3)"
            kategori = KATEGORI_MAP.get(row["category"])
            if kategori not in ai_rek.KATEGORIER:
                return None, f"rad {n}: category {row['category']!r} utanför ordet"
            year = row["year"]
            if year and not (year.isascii() and year.isdigit()
                             and 1000 <= int(year) <= 2100):
                return None, f"rad {n}: year {year!r} utanför dörrens domän"
            if not (row["title"] and row["review_source_url"]):
                return None, f"rad {n}: tom title/review_source_url"
            row["kategori"] = kategori
            row["nyckel"] = onska.wish_key(row["title"], row["author"])
            isbns[isbn] = n
            rows.append(row)
    if not rows:
        return None, "korpusen är tom"
    return rows, None


def read_library(url):
    """The PUBLIC shelf through the shared transport -> (graded cards,
    error|None). Non-200 is a hard error: a partial page is the WRONG
    library, and the taste profile built from it would be a lie."""
    status, body = _curl([url], timeout_s=GET_TIMEOUT_S)
    if status != 200:
        return None, f"bibliotek {status}"
    return pp.read_graded(body.decode("utf-8", "replace")), None


def smakprov(graded):
    """The taste-profile section: EVERY graded card with its rating — the
    prompt carries the graded library itself (MC 12602 scope row 2), not a
    paraphrase of it."""
    snitt = sum(c["rating"] for c in graded) / len(graded)
    rader = [f"- {c['title']} — {c['author'] or 'okänd författare'}: "
             f"{c['rating']} av 5" for c in graded]
    return (f"BETYGSSNITT över {len(graded)} betygssatta böcker: "
            f"{snitt:.2f}/5\n" + "\n".join(rader))


def build_prompt(graded, kandidater):
    """The whole ask in ONE user turn: profile + candidate rows + the strict
    answer contract. The model sees ONLY these rows to rank (the intent
    lives here; the guarantee lives in `_validera`)."""
    rader = [
        f"ISBN {r['isbn13']} | {r['title']} | {r['author']} | å {r['year'] or '?'}"
        f" | kategori {r['kategori']}\n  varför den kandideras: {r['why']}"
        f"\n  recensionscitat: {r['review_quote']}\n  fit-underlag: {r['fit_note']}"
        for r in kandidater]
    return (
        "Du är rekommendationsmotorn för Liselotts bokhylla. Nedan ligger "
        "hennes\nbetygssatta smakprofil — alla böcker hon betygssatt, med "
        "betyg — och\nkandidatlistan (corpus). Du får ENDAST ranka och "
        "motivera kandidater ur\ncorpus; hitta aldrig på en bok utanför "
        "listan.\n\n"
        "=== LISELOTTS BETYGSATTA BIBLIOTEK (smakprofilen) ===\n"
        + smakprov(graded) +
        "\n\n=== KANDIDATER (corpus — den ENDAST tillåtna mängden) ===\n"
        + "\n\n".join(rader) +
        "\n\nRanka VARJE kandidat efter hur väl den passar smakprofilen. "
        "Motivera\nvarje fit uttryckligen ur profilen: nämn vilka "
        "betygsatta böcker, genrer\n"
        "eller teman bedömningen vilar på "
        "(\"baserat på dina betyg på X\"-\nformuleringar).\n\nSvara med "
        "EXAKT en JSON-array — ingen text före eller efter, inga\n"
        "markdownstängsel:\n"
        '[{"isbn13": "<13 siffror, ordgrant ur corpus>", "fit": <flyttal '
        '0.0–1.0>,\n  "reason": "<motivering på svenska, 1–3 meningar>"}, '
        "...]\n\n"
        "Ordna fallande fit. Använd ENDAST isbn13-värden som finns "
        "ordgrant i\ncorpus ovan.\n")


def lane_ask(prompt, timeout_s=LANE_TIMEOUT_S):
    """ONE Lane E call, cover_pass._vision_post's envelope in shape (one
    model id, temp 0, reasoning_effort low on BOTH layers, content falling
    back to reasoning). Raises on any transport or shape failure — the
    runner answers with a refusal, never a retry loop (the §3 posture).
    `timeout_s` is the lane budget (MC 12616: the 300 s default died
    mid-generation, DA c4 P3 — now 600 s, moved by `--lane-timeout`).
    """
    payload = {"model": LANE_MODEL, "max_tokens": LANE_MAX_TOKENS,
               "temperature": 0,
               "reasoning_effort": "low",
               "chat_template_kwargs": {"reasoning_effort": "low"},
               "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(
        LANE_URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        msg = json.loads(r.read().decode("utf-8"))["choices"][0]["message"]
        return msg.get("content") or msg.get("reasoning") or ""


def parse_ranking(text):
    """Strict JSON parse: the answer must BE the array — no prose scraping,
    no fence salvage (a model that wraps in markdown is REFUSED, MC 12602's
    hostile-JSON leg). Raises ValueError when it isn't one list."""
    if not isinstance(text, str):
        raise ValueError("tomt svar")
    data = json.loads(text)                   # JSONDecodeError subclasses ValueError
    if not isinstance(data, list):
        raise ValueError("svaret är inte en JSON-array")
    return data


def _validera(ranking, by_isbn, agnas_isbn, *, say):
    """The anti-hallucination + fit gates, in CODE — carry N3 cited here:
    nothing can mint a POST row outside `by_isbn`, the loaded corpus.tsv
    rows. Title/author/year/source/kategori ride the CORPUS row, never the
    model's echo (a hostile answer cannot smuggle its own identity). Fit is
    refused outside [0,1], never clamped. Returns accepted door-shaped
    rows, best fit first."""
    godkanda = []
    for pos, rad in enumerate(ranking):
        def neka(why):
            say(f"REK NEKAD post {pos}: {why}")

        if not isinstance(rad, dict):
            neka("posten är inte ett objekt")
            continue
        isbn = rad.get("isbn13")
        if not (isinstance(isbn, str) and ISBN_FULL.fullmatch(isbn)
                and isbn.isascii()):
            neka("isbn13 saknas eller har fel form")
            continue
        ref = by_isbn.get(isbn)               # the OFFERED set is the
        if ref is None:                       # accepted set: N3 keeps rows
            if isbn in agnas_isbn:            # outside the corpus out, the
                neka(f"isbn13 {isbn} är en ägd bok som föll i join "     # F-C3-1
                     "— nekad (F-C3-1)")      # belt keeps owned drop-outs
            else:                             # out EVEN WHEN named back
                neka(f"isbn13 {isbn} finns inte i corpus")
            continue
        fit = rad.get("fit")
        if (isinstance(fit, bool) or not isinstance(fit, (int, float))
                or not math.isfinite(fit) or not 0.0 <= fit <= 1.0):
            neka(f"fit {fit!r} utanför [0,1] — nekad, aldrig kammad")
            continue
        reason = rad.get("reason")
        if not (isinstance(reason, str) and reason.strip()):
            neka("reason är tom")
            continue
        post = {"title": ref["title"],
                "author_name": ref["author"] or None,
                "isbn13": isbn,
                "year": int(ref["year"]) if ref["year"] else None,
                "reason": reason.strip(),
                "source": ref["review_source_url"],
                "fit": float(fit),
                "kategori": ref["kategori"]}   # kategori rides EVERY row
        felt = [k for k, v in post.items()
                if isinstance(v, str) and _har_kontrolltecken(v)]
        if felt:                              # N5, the payload-side belt
            neka(f"kontrolltecken i {','.join(felt)}")
            continue
        godkanda.append(post)
    godkanda.sort(key=lambda p: p["fit"], reverse=True)
    return godkanda


def dedupe_identitet(godkanda, *, say):
    """Carry N1, the citation for \"the runner MUST dedupe its OUTPUT by
    book identity (isbn UNION wish_key-normalized title+author) BEFORE
    POST\": the best-ranked row of each identity rides the POST, a twin is
    dropped — one identity per generation, never two rows whose rec_keys
    differ for one book."""
    sedda, ut = set(), []
    for post in godkanda:
        identiteter = {"i:" + post["isbn13"],
                       "k:" + onska.wish_key(post["title"],
                                             post["author_name"] or "")}
        if identiteter & sedda:
            say(f"REK DUBLETT bort: {post['isbn13']} ({post['title']})")
            continue
        sedda |= identiteter
        ut.append(post)
    return ut


def door_post(url, token, rows, *, full=False):
    """The ONE delivery, the retired pris runner's `door_post` posture
    (scripts/pris_vakt.py, deleted by MC 12606) on the shared transport:
    JSON on stdin via --data-binary @-, the token on
    `X-Ai-Rek-Token`, one try then loud. Returns (status, body-bytes).
    `full=True` (MC 12616, CLI `--full`) wraps the rows in the door's
    full-swap envelope `{"generation": rows}` — the POSTed list then IS
    the complete new generation; default mode is today's bare array."""
    payload = {"generation": rows} if full else rows
    return _curl_config(
        [("X-Ai-Rek-Token", token)],        # MC 12616: the secret rides a
        lambda config: ["--request", "POST",  # per-call 0600 --config file,
                        "--header",            # NEVER argv (DA c3 P2, the
                        "Content-Type: application/json",  # /proc/<curl> leak)
                        "--config", config,
                        "--data-binary", "@-", url],
        timeout_s=POST_TIMEOUT_S,
        stdin_data=json.dumps(payload).encode("utf-8"))


def run_pass(corpus_path, library_url, base, *, dry_run=False,
             get_library=read_library, lane=lane_ask, post=door_post,
             say=None, full=False):
    """One generation end-to-end; returns the process exit code. Seam
    layout is the retired pris runner's `run_tick` (every external touch
    injectable — the shape MC 12547 proved), so the
    whole contract tests with zero network. Exit: 0 ok; 2 input/config
    refused; 3 lane answer refused; 4 floor not met; 5 door refused;
    6 mix condition not met (nyhet AND klassiker owed, one not delivered).
    `full=True` (MC 12616, the CLI's `--full`, DEFAULT off) rides the
    door's full-swap envelope — every gate above is IDENTICAL, only the
    delivery mode changes; the rows this run validates ARE the complete
    new generation the door sweeps against."""
    say = say or (lambda line: print(line, flush=True))

    rows, fel = read_corpus(corpus_path)
    if rows is None:
        say(f"ALARM korpus avvisad: {fel} — noll POST")
        return 2
    graded, fel = get_library(library_url)
    if graded is None:
        say(f"ALARM bibliotek avvisat: {fel} — noll POST")
        return 2
    if not graded:                            # MC 12602 scope row 2: the
        say("ALARM smakprofil tom: biblioteket gav noll betygssatta rader "
            "— vägrar POST (ingen 'baserat på hyllan' utan hyllan)")
        return 2                              # refuse BEFORE the lane ask

    agda_nycklar = {onska.wish_key(c["title"], c["author"]) for c in graded}
    agda_isbn = {c["isbn13"] for c in graded if c.get("isbn13")}
    kandidater = [r for r in rows
                  if r["nyckel"] not in agda_nycklar
                  and r["isbn13"] not in agda_isbn]
    # F-C3-1 (DA c3 item 3, the tester's L11): the accepted set IS the
    # OFFERED set — an isbn naming a corpus row the join DROPPED as owned
    # is refused post-parse even when the model names it back (the belt
    # runs after the prompt was already clean; the prompt is intent, this
    # is the guarantee).
    by_isbn = {r["isbn13"]: r for r in kandidater}
    agnas_isbn = {r["isbn13"] for r in rows if r["isbn13"] not in by_isbn}
    say(f"REK korpus={len(rows)} drogs_bort={len(rows) - len(kandidater)} "
        f"kandidater={len(kandidater)} betygssatta={len(graded)}")
    if not kandidater:
        say("ALARM alla kandidater finns redan på hyllan — noll POST")
        return 2

    try:
        ranking = parse_ranking(lane(build_prompt(graded, kandidater)))
    except (ValueError, KeyError, urllib.error.URLError, OSError) as e:
        say(f"ALARM lane-svar avvisas: {type(e).__name__}: {e} — noll POST")
        return 3
    godkanda = dedupe_identitet(
        _validera(ranking, by_isbn, agnas_isbn, say=say), say=say)
    say(f"REK godkanda={len(godkanda)} av {len(ranking)} poster "
        f"(golv {MIN_OUTPUT_ROWS})")
    if len(godkanda) < MIN_OUTPUT_ROWS:       # thin generation = failed one
        say(f"ALARM för tunn generation: {len(godkanda)} < {MIN_OUTPUT_ROWS} "
            "rader — vägrar POST")
        return 4
    kategorier = {p["kategori"] for p in godkanda}
    if not {"nyhet", "klassiker"} <= kategorier:      # owner scope: "newly
        saknade = sorted({"nyhet", "klassiker"} - kategorier)   # released
        say(f"ALARM blandningsvillkor: output saknar {','.join(saknade)} "
            "— minst en nyhet OCH en klassiker krävs, vägrar POST")        # books
        return 6                              # as well as classics
    if dry_run:                               # prints; the ONLY skipped POST
        say("DRY-RUN-RADER " + json.dumps(godkanda, ensure_ascii=False))
        say(f"DRY-RUN: {len(godkanda)} rankade rader utskrivna, INGET POSTAT")
        return 0

    token = os.environ.get(ENV_TOKEN) or ""
    if not TOKEN_SHAPE.fullmatch(token):      # the env NAME is named, the
        say(f"ALARM {ENV_TOKEN} saknas eller har fel form (64 hex) "
            "— vägrar POST")                  # VALUE is never echoed
        return 2
    status, body = post(f"{base}/ai-rek", token, godkanda, full=full)
    if not 200 <= status < 300:
        say(f"ALARM dörren svarade {status}: {body[:200]!r} — generationen "
            "landade inte")
        return 5
    say(f"REK POST OK status={status} "
        f"kvittering={body.decode('utf-8', 'replace')[:200]}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--library", default=None,
                    help="public shelf URL (default $LISELOTT_URL/bibliotek, "
                         f"else {BASE_DEFAULT}/bibliotek)")
    ap.add_argument("--corpus", required=True, help="corpus.tsv path")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the ranked rows; POST nothing")
    ap.add_argument("--full", action="store_true",
                    help="MC 12616: POST the rows as the COMPLETE new "
                         "generation (full-swap envelope) — the door "
                         "deletes state='new' rows absent from it; DEFAULT "
                         "off = today's plain upsert")
    ap.add_argument("--lane-timeout", type=int, default=LANE_TIMEOUT_S,
                    help=f"Lane E ask budget in seconds (default "
                         f"{LANE_TIMEOUT_S}; the shipped 300 died mid-"
                         "generation, DA c4 P3)")
    args = ap.parse_args(argv)
    base = (os.environ.get(ENV_URL) or BASE_DEFAULT).rstrip("/")
    library = args.library or f"{base}/bibliotek"
    return run_pass(args.corpus, library, base, dry_run=args.dry_run,
                    full=args.full,
                    lane=lambda prompt: lane_ask(prompt,
                                                 timeout_s=args.lane_timeout))


if __name__ == "__main__":
    raise SystemExit(main())
