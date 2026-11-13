#!/usr/bin/env python3
"""S12 — bounded fleet-browser cover pass over the build DB (OQ-2 residual fill,
owner ruling 2026-11-12, MC 12466). What the automated search finds and both
gates confirm is stored here; what it cannot confirm stays NULL for Liselott's
manual hitta-omslag run — an honest report, not a guessed cover.

ONE mechanism per concern, reused not forked:
  - page -> cover url:  app.omslag.extract_cover_url (THE extractor)
  - bytes -> cover:     app.enrich.store_cover (THE normalizer + 1x1 gate),
                        written with cover_source='manual-url' — the value the
                        admin hitta-omslag path already writes and the schema
                        CHECK already allows (no new CHECK value, no migration)
  - http:               app.enrich.http_get (ONE transport, scheme-checked,
                        900 kB cap)
  - "this book's cover, clearly": the gates in scripts/cover_gates.py (imported
    below and re-exported for the tests): the candidate PAGE must name the book,
    and the stored IMAGE must pass a Lane-E verbatim transcription check — the
    vision model REPORTS the printed words, the gate JUDGES them (a VLM asked
    "is this right?" rubber-stamps, MC#524). Wrong covers are worse than none.

Bandit guardrails: >=1 s between external fetches; a host that answers 429/4xx
or refuses transport is added to an in-memory blocklist and never retried (no
evading walls); caps: books attempted AND wall minutes, whichever binds first.

Run against the build DB only:
  LISELOTT_DATA_DIR=/home/claudecode/liselott-build \
      .venv/bin/python scripts/cover_pass.py --csv <report.csv>
  # next wave: also pass --skip-report <previous report.csv>
"""
import argparse
import base64
import csv
import io
import json
import os
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # the repo's script idiom
sys.path.insert(0, str(ROOT))

from app import db, enrich, omslag
from scripts.cover_gates import (  # re-export surface, the enrich.py idiom
    STOP_TOKENS, author_key, blocked_key, cover_confirms, normalize,
    page_relevant, rank_candidates, rank_one, sig_tokens)

FIRECRAWL = os.environ.get("FIRECRAWL_SEARCH_URL",
                           "http://192.168.5.20:3002/v1/search")
VISION_URL = os.environ.get("DESCRIBE_IMAGE_ENDPOINT",
                            "http://192.168.5.223:8888/v1/chat/completions")
VISION_MODEL = os.environ.get("DESCRIBE_IMAGE_MODEL", "qwen3.8-flash-next")
POLITE_S = 1.0            # min seconds between external fetches
MAX_CANDIDATES = 4        # candidate pages fetched per book

_last_fetch = [0.0]


def pace():
    """Polite pacing on the ONE clock every external call goes through."""
    wait = POLITE_S - (time.monotonic() - _last_fetch[0])
    if wait > 0:
        time.sleep(wait)
    _last_fetch[0] = time.monotonic()


# ---- thin IO seams (every one injectable for the offline tests) --------------

def search(query, *, post=None):
    """firecrawl on noa (no key): [{url,title,description}]. None on failure
    (after one retry) — an engine error must not masquerade as "no hits"."""
    post = post or _search_post
    for attempt in (0, 1):
        try:
            return post(query)
        except Exception:
            if attempt:
                return None
    return None


def _search_post(query):
    pace()
    body = json.dumps({"query": query, "limit": 6}).encode()
    req = urllib.request.Request(FIRECRAWL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8")).get("data") or []


VISION_ASK = (
    "Describe literally what is visible in this image. Report only what is "
    "actually rendered: transcribe verbatim every word printed on it, then "
    "say in one line what the image shows (bokomslag, portratt, logo, ...). "
    "Do not guess anything you cannot see; if unreadable, say so.")


def vision_transcribe(jpeg_bytes, *, post=None):
    """Lane E verbatim transcription — the describe-image skill's own envelope
    (effort low on both layers, ADR-0080). None when vision is dark: an
    unconfirmable cover then stays NULL, it is never guessed past."""
    try:
        return (post or _vision_post)(jpeg_bytes)
    except Exception:
        return None


def _vision_post(jpeg_bytes):
    payload = {"model": VISION_MODEL, "max_tokens": 250, "temperature": 0,
               "reasoning_effort": "low",
               "chat_template_kwargs": {"reasoning_effort": "low"},
               "messages": [{"role": "user", "content": [
                   {"type": "image_url", "image_url": {
                       "url": "data:image/jpeg;base64,"
                       + base64.b64encode(jpeg_bytes).decode()}},
                   {"type": "text", "text": VISION_ASK}]}]}
    req = urllib.request.Request(
        VISION_URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        msg = json.loads(r.read().decode("utf-8"))["choices"][0]["message"]
        return msg.get("content") or msg.get("reasoning") or ""


def downscale_for_vision(data):
    """<=1280 long edge JPEG — the describe-image skill's budget rule. The
    FULL bytes go to store_cover; only the look at them is downscaled."""
    from PIL import Image
    img = enrich.validate_cover_bytes(data).convert("RGB")
    img.thumbnail((1280, 1280))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()


# ---- the pass ----------------------------------------------------------------

def attempt_book(conn, book, *, searcher=search, fetch=enrich.http_get,
                 describer=vision_transcribe, blocked=None):
    """One book. Every failure path returns a report row instead of raising;
    'covered' happens only through store_cover on bytes both gates approved."""
    blocked = blocked if blocked is not None else set()
    bid, title, author = book["id"], book["title"], book["author"] or ""
    isbns = [i for i in (book["isbn13"], book["isbn10"]) if i]
    row = {"book_id": bid, "title": title, "author": author,
           "isbn13": book["isbn13"] or "", "outcome": "unresolved",
           "detail": "", "cover_source": "", "page_url": "", "image_url": ""}
    hits = searcher(" ".join(x for x in (title, author, "bokomslag") if x))
    if hits is None:
        row["detail"] = "sokfel hos fjarrsokmotorn (2 fosterk)"
        return row
    if not hits:
        row["detail"] = "sokningen gav ingen traff"
        return row
    for url in rank_candidates(hits, title, isbns, blocked)[:MAX_CANDIDATES]:
        if blocked_key(url) in blocked:      # walled mid-book by an earlier cand
            continue
        try:
            pace()
            page = fetch(url, timeout=8.0, attempts=1).decode("utf-8", "replace")
        except (enrich.ProviderUnavailable, ValueError):
            # ValueError covers UnicodeEncodeError on raw-åö urls (measured
            # 2026-11-13): a malformed candidate is a bad candidate, nothing more
            blocked.add(blocked_key(url))       # a wall is a wall: never retried
            continue
        ok, why = page_relevant(page, title, author, isbns)
        if not ok:
            continue
        cov = omslag.extract_cover_url(page, url)
        if not cov:
            row["detail"] = f"ingen omslagsbild pa sidan ({url}): {why}"
            continue
        try:
            pace()
            image = fetch(cov, timeout=8.0, attempts=1)
        except (enrich.ProviderUnavailable, ValueError):  # BodyTooLarge is one
            row["detail"] = f"omslagsbilden hamtades ej: {cov}"  # too: cap is cap
            continue
        if omslag.image_kind(image) is None:
            row["detail"] = f"det sidan pekade pa ar ingen bild: {cov}"
            continue
        try:
            look = downscale_for_vision(image)
        except enrich.CoverRejected as e:
            row["detail"] = f"bilden ogillades fore inspektion: {e}"
            continue
        desc = describer(look)
        if desc is None:
            row["detail"] = "vision morkt — inget bekraftas, inget lagras"
            return row                          # and trying on blind is worse
        ok, vwhy = cover_confirms(desc, title, author)
        if not ok:
            row["detail"] = f"kandidat avvisad ({url}): {vwhy}"
            continue
        try:
            rel = enrich.store_cover(conn, bid, image, "manual-url")
        except enrich.CoverRejected as e:
            row["detail"] = f"normaliseringen nekade bilden: {e}"
            continue
        row.update(outcome="covered", detail=f"{rel} via {why} + {vwhy}",
                   cover_source="manual-url", page_url=url, image_url=cov)
        return row
    if not row["detail"]:
        row["detail"] = "ingen kandidat stark nog genom sid- och bildgrinden"
    return row


REPORT_FIELDS = ["book_id", "title", "author", "isbn13", "outcome", "detail",
                 "cover_source", "page_url", "image_url"]


def prior_wave_ids(paths):
    """book_ids already attempted by earlier wave reports. A second wave
    continues where the last one ended: the report CSV is the wave record,
    so skipping its ids is the next-batch selector (an offset number would
    drift the moment a manual cover lands between waves)."""
    ids = set()
    for p in paths:
        with open(p, newline="") as fh:
            ids |= {int(r["book_id"]) for r in csv.DictReader(fh)}
    return ids


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", required=True,
                    help="report path (MC evidence, not repo content)")
    ap.add_argument("--books", type=int, default=60, help="max books attempted")
    ap.add_argument("--minutes", type=float, default=60.0, help="wall budget")
    ap.add_argument("--skip-report", nargs="+", default=[], metavar="CSV",
                    help="earlier wave report CSVs: their book_ids are already "
                         "attempted and are skipped (the next-batch selector)")
    args = ap.parse_args(argv)

    start = time.monotonic()
    conn = db.connect()
    db.init_db(conn)                     # idempotent; the ONE schema entry point
    conn.row_factory = sqlite3.Row
    todo = conn.execute(
        "SELECT b.id, b.title, b.status,"
        " (SELECT a.name FROM book_author ba JOIN author a ON a.id=ba.author_id"
        "  WHERE ba.book_id=b.id ORDER BY ba.rowid LIMIT 1) AS author,"
        " b.isbn13, b.isbn10 FROM book b"
        " WHERE b.cover_path IS NULL OR b.cover_path = ''"
        " ORDER BY CASE b.status WHEN 'read' THEN 0 ELSE 1 END, b.id").fetchall()
    if args.skip_report:
        skip = prior_wave_ids(args.skip_report)
        todo = [b for b in todo if b["id"] not in skip]
    before = conn.execute("SELECT COUNT(*) FROM book"
                          " WHERE cover_path IS NOT NULL").fetchone()[0]

    os.makedirs(os.path.dirname(os.path.abspath(args.csv)), exist_ok=True)
    blocked, attempted = set(), 0
    with open(args.csv, "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=REPORT_FIELDS)
        wr.writeheader()
        for book in todo:
            if attempted >= args.books or time.monotonic() - start >= args.minutes * 60:
                break
            wr.writerow(attempt_book(conn, dict(book), blocked=blocked))
            fh.flush()                             # a killed run keeps its rows
            attempted += 1
    after = conn.execute("SELECT COUNT(*) FROM book"
                         " WHERE cover_path IS NOT NULL").fetchone()[0]
    print(f"attempted={attempted} covers_before={before} covers_after={after} "
          f"delta={after - before} wall={time.monotonic() - start:.0f}s "
          f"report={args.csv}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
