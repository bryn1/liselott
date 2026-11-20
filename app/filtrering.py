"""MC 12551 — the PUBLIC shelf's filters (owner 2026-11-15, verbatim: "The
public page needs filter by score, year, search by author, title and year").

ONE narrowing step over rows the caller ALREADY fetched through the ONE public
filter (`books.load_books(public_only=True)` under `books.PUBLIC_SET_SQL`, MC
12501). This module runs no query of its own — not for the rows, not for the
year list — so a filtered shelf can never be WIDER than the public set it
narrows: a param only ever REMOVES rows, and an unrated book has no path onto
an anonymous page through this door.

The private `/sok` (§7's five keys, `app/search.py`) is untouched and stays
the owner's mechanism. The public `q` is the plain free text the owner named —
TITLE OR AUTHOR — matched with the SAME fold `app.search` matches with
(`app.text.fold`: case-fold + diacritic-fold, so å≈a and NATT=natt). Matching
is a substring test over rows already in hand: there is no SQL `LIKE` here, so
"%", "_" and a quote are LITERAL characters by construction, never wildcards
(the legs in tests/test_public_filter.py pin it).
"""
import re

from app.books import shelf_year
from app.text import fold

# The three params, exactly as the card names them. An invalid value is the
# SAME as an absent one (§9's calm page: never a 500, never a wider answer),
# so both regexes are full-match shape tests and nothing else.
BETYG_RE = re.compile(r"[1-5]")          # the same domain routes.GRADE_RE writes
AR_RE = re.compile(r"\d{4}")             # a shelf year is four digits
EMPTY = {"betyg": None, "ar": None, "q": "", "aktiv": False}


def parse(args):
    """Query params -> the filter the shelf applies. `args` is the request's
    read-only multi-dict; a repeated name takes its first value (what a
    browser sends). `aktiv` says whether ANY of the three actually filters —
    the page's own "Inga träffar" line and the form's selected states read
    it, so no template re-derives the rule."""
    out = dict(EMPTY)
    betyg = str(args.get("betyg") or "").strip()
    if BETYG_RE.fullmatch(betyg):
        out["betyg"] = int(betyg)
    ar = str(args.get("ar") or "").strip()
    if AR_RE.fullmatch(ar):
        out["ar"] = int(ar)
    out["q"] = str(args.get("q") or "").strip()
    out["aktiv"] = bool(out["betyg"] or out["ar"] or out["q"])
    return out


def matches_text(bok, folded_query):
    """§7's fold on BOTH sides, over the two fields the owner named."""
    haystacks = [fold(bok["title"])] + [fold(a) for a in bok["authors"]]
    return any(folded_query in h for h in haystacks if h)


def years(bocker):
    """The shelf years PRESENT in the rows handed in — newest first, the way
    the sections run. Built from the SAME rows the shelf renders from, never
    from a query over the book table: a year only a PRIVATE book populated
    must never reach the form's <option> list (an option value is a render of
    private data; the leg pins it). The wish rows carry the 0 sentinel, not a
    year, so they contribute nothing here."""
    return sorted({year for year in (shelf_year(b) for b in bocker) if year},
                  reverse=True)


def narrow(bocker, filtr):
    """The rows the reader asked to see, out of the rows she was ALLOWED to
    see. Rows carrying REAL data — every read row, and since MC 12733 the
    RATED 'aborted' row the F-E ruling lets stand (its year is the 0
    sentinel, so any ?ar= lawfully excludes it) — face all three params,
    combined with AND. The exemption belongs to the WISHLIST alone (the ONE
    wish law, F-A): wish rows are BORN with neither rating nor read year,
    and the ruling made them public AS THEY ARE, so no betyg/ar param
    removes them (and none can leak one either: they are already public).
    The pre-W1 test `!= 'read'` is retired — with the widened domain it would
    have exempted 'reading'/'aborted' rows from the params too."""
    if not filtr["aktiv"]:
        return list(bocker)
    needle = fold(filtr["q"])
    out = []
    for bok in bocker:
        if needle and not matches_text(bok, needle):
            continue
        if bok["status"] == "wishlist":       # the wishlist: q was its only test
            out.append(bok)
            continue
        if filtr["betyg"] is not None and bok["rating"] != filtr["betyg"]:
            continue
        if filtr["ar"] is not None and shelf_year(bok) != filtr["ar"]:
            continue
        out.append(bok)
    return out
