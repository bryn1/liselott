"""Search (§7, cycle-1 verbatim — the ONE search mechanism).

`parse_query` is pure: it classifies a raw query into (kind, value) without
touching the DB, so the five keys are testable offline. `search()` runs the
parsed query. Text is matched by folding BOTH sides (NFKD, diacritics removed,
casefolded) — §7's "Swedish å≈a … but match raw too": one fold applied to the
query and to the stored value makes the accented and unaccented spellings the
same string, so raw input is matched too. SQLite's LIKE only case-folds ASCII,
so the fold runs in Python over the small corpus (724 rows, one scan) rather
than pretending COLLATE NOCASE handles åäö."""
import re
import unicodedata

from app.books import load_books, sort_by_read_date
from app.text import fold

# §7's ISBN token: an optional 978/979 prefix, nine digits, one check char.
_ISBN_TOKEN_RE = re.compile(r"^(?:97[89])?\d{9}[\dX]$")
_YEAR_RE = re.compile(r"^\d{4}$")
# §7: a 4-digit token alone is a year only inside this window.
YEAR_MIN, YEAR_MAX = 1400, 2099

# The kinds parse_query answers with; search() handles exactly these.
KINDS = ("empty", "isbn", "year", "genre", "text")


def _mod10_check(nine_or_twelve: str) -> str:
    """EAN/ISBN-13 check digit: alternating weights 1 and 3 over the digits."""
    total = sum(int(d) * (1 if i % 2 == 0 else 3)
                for i, d in enumerate(nine_or_twelve))
    return str((10 - total % 10) % 10)


def isbn10_to_13(isbn10: str):
    """§7's EAN conversion: 978 + the first nine digits + a computed mod-10
    check digit (never copied from the 10-digit form — the prefix changes it)."""
    body = re.sub(r"[\s-]", "", str(isbn10 or "")).upper()
    if len(body) != 10 or not re.match(r"^\d{9}[\dX]$", body):
        return None
    return f"978{body[:9]}{_mod10_check('978' + body[:9])}"


def normalize_isbn(text):
    """The §7 ISBN test on one token: strip spaces/hyphens, case-fold the X,
    match the shape, then validate. Returns (isbn13, isbn10_or_None) or None.

    The validation §7 pins is the CHECK DIGIT of the 13-digit form (mod-10):
    a bad one means the token was not an ISBN after all, and §7 sends it to
    the text path — a typo becomes a word, never an empty result set. The
    10-digit form is NOT gated on mod-11, deliberately and measured: the
    diary's own Stöld ISBN-10 9198559699 (the recorded OL fixture) is not
    mod-11-valid (weighted sum 355, 355 mod 11 = 3), so requiring it would
    answer "no hits" on a real ISBN she owns."""
    token = re.sub(r"[\s-]", "", str(text or "")).upper()
    if not _ISBN_TOKEN_RE.match(token):
        return None
    if len(token) == 13:
        return (token, None) if _mod10_check(token[:12]) == token[12] else None
    return (isbn10_to_13(token), token)


def parse_query(q, genre_names=()):
    """Raw query -> (kind, value); kind in KINDS.

    genre_names is the vocabulary the caller already read from the DB (§7: "a
    token equal to a genre name ... also filters genre"); folding both sides
    makes the comparison case- and accent-insensitive. Keeping it an argument
    is what lets this function stay pure — there is no second genre list here.
    """
    text = unicodedata.normalize("NFKC", str(q or "")).strip()
    if not text:
        return ("empty", "")
    isbn = normalize_isbn(text)
    if isbn:
        return ("isbn", isbn[0])
    if _YEAR_RE.match(text) and YEAR_MIN <= int(text) <= YEAR_MAX:
        return ("year", int(text))
    folded = fold(text)
    for name in genre_names:
        if fold(name) == folded:
            return ("genre", name)
    return ("text", folded)


def _matches_text(book, folded_query):
    """§7: LIKE over title, canonical author names and genre names, folded."""
    haystacks = [fold(book["title"])]
    haystacks += [fold(a) for a in book["authors"]]
    haystacks += [fold(g) for g in book["genres"]]
    return any(folded_query in h for h in haystacks)


def search(conn, query, genre_names=None):
    """The one search entry point: parsed query -> the book rows it hits."""
    if genre_names is None:
        genre_names = [r[0] for r in conn.execute(
            "SELECT name FROM genre ORDER BY name")]
    kind, value = parse_query(query, genre_names)
    if kind == "empty":
        return []
    books = load_books(conn)
    if kind == "isbn":
        hits = [b for b in books if _hits_isbn(b, value)]
    elif kind == "year":
        hits = [b for b in books
                if b["year"] == value or b["read_year"] == value]
    elif kind == "genre":
        needle = fold(value)
        hits = [b for b in books if any(fold(g) == needle for g in b["genres"])]
    else:
        hits = [b for b in books if _matches_text(b, value)]
    return sort_by_read_date(hits)


def _hits_isbn(book, isbn13):
    """Both stored columns, plus the computed one (§7): a row that stores only
    isbn10 is found through its 13-digit form, so the reader never has to know
    which form she typed."""
    if book["isbn13"] == isbn13:
        return True
    if book["isbn10"] and isbn10_to_13(book["isbn10"]) == isbn13:
        return True
    return False
