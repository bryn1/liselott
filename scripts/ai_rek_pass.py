#!/usr/bin/env python3
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
  taste          zero graded rows from --library => REFUSE, loud, non-zero,
                 BEFORE the lane ask (MC 12602 scope row 2: "based on the
                 current graded library" must be real).

Delivery: POST {base}/ai-rek through curl_transport (ONE transport for
both door runners — this card's shared extraction), `X-Ai-Rek-Token: ` from
env AI_REC_DOOR_TOKEN, 64-hex asserted through the door's OWN TOKEN_SHAPE,
the value never echoed. --dry-run prints the ranked JSON and POSTS NOTHING
(the door POST is the ONLY thing dry-run skips — the shelf read and the
lane ask still run, else the demo would prove nothing).

KNOWN LIMITS, documented not papered over:
  FULL-REPLACEMENT SWEEP (MC 12602 scope row 1): the door supports NO
  delete verb — app/ai_rek.ingest is upsert-only and no route retires a
  state='new' row. Rows still `new` that are ABSENT from this generation's
  output therefore survive on the page (accept/decline rows are never
  touched here, as required). The contract gap, named exactly: DELETE-by-
  absence needs a door route (or an ingest flag) that does not exist;
  building it means touching app code, which this card forbids.
  DECLINE-FLIP RACE (carry N2, app-side P3): unreachable from this runner
  lane — the runner is the single writer; the race needs the owner's
  browser flip landing mid-ingest, which is app-side.
  OWNED-BOOK TITLE SPELLINGS (measured on the live demo 2026-11-17): the
  corpus ships some titles with an English subtitle tail while the shelf
  grades the plain title — wish_key cannot unify the two spellings, so one
  already-graded book was offered (the lane's own reason even cited her
  rating for it). The mechanism that fixes it is the app's ONLY spelling
  mechanism — the alias table (seed.app_aliases, owner-placed, empty on
  this host); this runner deliberately adds NO second title normalizer
  beside the §5.3 chain. (The diary's own strings are named nowhere here:
  the exposure gate, scripts/exposure_check.py, counts this file.)
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
from scripts.curl_transport import _curl     # THE shared door transport

ENV_URL, ENV_TOKEN = "LISELOTT_URL", ai_rek.AI_REK_TOKEN_ENV
BASE_DEFAULT = "https://sibbamala.com/liselott"
GET_TIMEOUT_S, POST_TIMEOUT_S, LANE_TIMEOUT_S = 15, 30, 300
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


def lane_ask(prompt):
    """ONE Lane E call, cover_pass._vision_post's envelope in shape (one
    model id, temp 0, reasoning_effort low on BOTH layers, content falling
    back to reasoning). Raises on any transport or shape failure — the
    runner answers with a refusal, never a retry loop (the §3 posture).
    """
    payload = {"model": LANE_MODEL, "max_tokens": LANE_MAX_TOKENS,
               "temperature": 0,
               "reasoning_effort": "low",
               "chat_template_kwargs": {"reasoning_effort": "low"},
               "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(
        LANE_URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=LANE_TIMEOUT_S) as r:
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


def _validera(ranking, by_isbn, *, say):
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
        ref = by_isbn.get(isbn)
        if ref is None:                       # ANTI-HALLUCINATION (N3): the
            neka(f"isbn13 {isbn} finns inte i corpus")   # corpus IS the set
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


def door_post(url, token, rows):
    """The ONE delivery, the pris_vakt.door_post posture on the shared
    transport: JSON array on stdin via --data-binary @-, the token on
    `X-Ai-Rek-Token`, one try then loud. Returns (status, body-bytes)."""
    return _curl(
        ["--request", "POST", "--header", "Content-Type: application/json",
         "--header", "X-Ai-Rek-Token: " + token,
         "--data-binary", "@-", url],
        timeout_s=POST_TIMEOUT_S,
        stdin_data=json.dumps(rows).encode("utf-8"))


def run_pass(corpus_path, library_url, base, *, dry_run=False,
             get_library=read_library, lane=lane_ask, post=door_post,
             say=None):
    """One generation end-to-end; returns the process exit code. Seam
    layout is pris_vakt.run_tick's: every external touch injectable, so the
    whole contract tests with zero network. Exit: 0 ok; 2 input/config
    refused; 3 lane answer refused; 4 floor not met; 5 door refused."""
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
    by_isbn = {r["isbn13"]: r for r in rows}
    kandidater = [r for r in rows
                  if r["nyckel"] not in agda_nycklar
                  and r["isbn13"] not in agda_isbn]
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
    godkanda = dedupe_identitet(_validera(ranking, by_isbn, say=say), say=say)
    say(f"REK godkanda={len(godkanda)} av {len(ranking)} poster "
        f"(golv {MIN_OUTPUT_ROWS})")
    if len(godkanda) < MIN_OUTPUT_ROWS:       # thin generation = failed one
        say(f"ALARM för tunn generation: {len(godkanda)} < {MIN_OUTPUT_ROWS} "
            "rader — vägrar POST")
        return 4

    if dry_run:                               # prints; the ONLY skipped POST
        say("DRY-RUN-RADER " + json.dumps(godkanda, ensure_ascii=False))
        say(f"DRY-RUN: {len(godkanda)} rankade rader utskrivna, INGET POSTAT")
        return 0

    token = os.environ.get(ENV_TOKEN) or ""
    if not TOKEN_SHAPE.fullmatch(token):      # the env NAME is named, the
        say(f"ALARM {ENV_TOKEN} saknas eller har fel form (64 hex) "
            "— vägrar POST")                  # VALUE is never echoed
        return 2
    status, body = post(f"{base}/ai-rek", token, godkanda)
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
    args = ap.parse_args(argv)
    base = (os.environ.get(ENV_URL) or BASE_DEFAULT).rstrip("/")
    library = args.library or f"{base}/bibliotek"
    return run_pass(args.corpus, library, base, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
