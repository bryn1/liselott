"""S12 cover pass — the PURE gates and the candidate ranker, split out of
scripts/cover_pass.py per file hygiene (one concern per file; the IO/driver
lives there and re-exports these names). Every function here is string-only:
the offline tests in tests/test_cover_pass.py ARE their specification."""
import re
import unicodedata
from urllib.parse import quote, urlsplit

STOP_TOKENS = {"och", "pa", "i", "de", "den", "det", "en", "ett", "av", "till",
               "som", "under", "over", "mellan", "for", "med", "vid", "at",
               "hos", "fran", "din", "min", "sin", "var", "har", "kan", "sa",
               "om", "nu", "da", "ej", "icke", "inte", "alla", "ingen"}


def normalize(text):
    """casefold, strip diacritics (slug-safe: dar == där), non-alphanumeric to
    spaces — the one comparison form every gate and ranker shares."""
    text = unicodedata.normalize("NFD", str(text or "").casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def sig_tokens(title):
    """Tokens that identify the book: >=3 chars, not a Swedish stop word."""
    return [t for t in normalize(title).split()
            if len(t) >= 3 and t not in STOP_TOKENS]


def author_key(author):
    """Surname (last token) + any distinctive given-name token: an image
    prints one of these the moment it prints the author at all."""
    toks = normalize(author).split()
    if not toks:
        return set()
    return {toks[-1]} | {t for t in toks if len(t) >= 4}


def _heads(page_text):
    """The page's self-reported headings: <title> and og:title in either
    attribute order — what a product page says it is, in its own words."""
    found = re.findall(
        r"<title[^>]*>(.*?)</title>"
        r"|<meta[^>]+og:title[^>]*content=[\"'](.*?)[\"']"
        r"|<meta[^>]+content=[\"'](.*?)[\"'][^>]+og:title",
        page_text, re.I | re.S)
    return normalize(" ".join(g for grp in found for g in grp if g))


def page_relevant(page_text, title, author, isbns):
    """The page names THIS book: its own ISBN is in the bytes (product pages
    carry it, hyphenation aside), or the page headings carry every distinctive
    title token plus the author. (bool, why) — a refusal names what was absent."""
    flat = page_text.replace("-", "")
    for isbn in isbns:
        if isbn and isbn.replace("-", "") in flat:
            return True, f"isbn {isbn} i sidan"
    hay = _heads(page_text)
    missing = [t for t in sig_tokens(title) if t not in hay]
    if missing:
        return False, "titel ord saknas i sidhuvud: " + ",".join(missing[:3])
    if author_key(author) and not any(a in hay for a in author_key(author)):
        return False, "forfattare saknas i sidhuvud"
    return True, "titel+forfattare i sidhuvud"


def cover_confirms(desc, title, author):
    """(bool, why) over the vision model's literal transcription: most
    distinctive title tokens AND an author token must be words the image
    actually prints. A portrait or a logo transcribes to nothing book-shaped
    and fails here (measured on the 2026-11-13 calibration probes)."""
    d = normalize(desc)
    toks = sig_tokens(title)
    if not toks:
        return False, "titeln har inga sarskiljande ord"
    hits = [t for t in toks if t in d]
    need = max(1, -(-6 * len(toks) // 10))          # ceil(0.6 * len)
    if len(hits) < need:
        return False, f"bara {len(hits)}/{len(toks)} titelord tryckta i bilden"
    if author_key(author) and not any(a in d for a in author_key(author)):
        return False, "forfattare trycks inte i bilden"
    return True, "titel+forfattare tryckta i bilden"


def blocked_key(url):
    return urlsplit(url).netloc.lower().removeprefix("www.")


def rank_one(hit, book_title, isbns):
    """3 = a url carrying the book's own ISBN (a product page for exactly this
    book), 2 = the search result repeats the whole distinctive title, 1 = other."""
    url, hit_title = (hit.get("url") or "").lower(), hit.get("title") or ""
    if any(isbn and isbn.replace("-", "") in url.replace("-", "") for isbn in isbns):
        return 3
    toks = sig_tokens(book_title)
    if toks and all(t in normalize(hit_title) for t in toks):
        return 2
    return 1


def rank_candidates(hits, book_title, isbns, blocked):
    """Best-shaped candidates first, search-engine order breaks ties; blocked
    hosts (walls) and .pdfs never appear. Paths are percent-encoded on the way
    out (bokbörsen serves raw-åö urls; urllib's request line is ascii-only,
    measured UnicodeEncodeError 2026-11-13)."""
    scored = [(rank_one(h, book_title, isbns), i, h.get("url") or "")
              for i, h in enumerate(hits) if h.get("url")]
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [urlunsplit_safe(url) for _, _, url in scored
            if blocked_key(url) not in blocked
            and not url.lower().split("?")[0].endswith(".pdf")]


def urlunsplit_safe(url):
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}" + quote(parts.path, safe="/%:@&=+$,~-_*!()") \
        + (f"?{parts.query}" if parts.query else "")
