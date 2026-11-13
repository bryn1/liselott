"""Provider plumbing for enrichment (§10, F-1: enrichment runs where the plan
says it runs — the VM350 build passes AND the app's own clients inside its
jail). ONE http mechanism for every provider AND for the admin hitta-omslag
fetcher: stdlib urllib, 3 s timeout, retries with exponential backoff on
429/5xx, a byte cap on every body it reads. A 429 that survives the retries
surfaces as RateLimited so a caller can act on it (the gb cooldown, T3.2)
without a second http path. Bodies are capped, never streamed into memory
blind: an over-budget body raises BodyTooLarge naming the budget."""
import difflib
import io
import json
import re
import time
import unicodedata
import urllib.error
import urllib.request
from urllib.parse import urlsplit

# ASCII ONLY: urllib encodes headers as latin-1, so one em dash here would
# kill every real request (UnicodeEncodeError) while fixture transports, which
# never encode a header, stay green — the live smoke caught it (guarded in
# tests/test_enrich_ol.py).
USER_AGENT = "liselott-bokhylla/1.0 (personal book diary)"

# Lane fact (§10, P1-1): every byte transfer INTO the app is chunked below a
# 900,000-byte budget; the same number bounds what the app itself accepts to
# read back from any single response.
MAX_BODY = 900_000


class ProviderUnavailable(Exception):
    """The provider could not be consulted (DNS/timeout/refused/definitive 4xx).
    Callers record the attempt in tried_providers; nothing here crashes a row."""


class RateLimited(ProviderUnavailable):
    """429 after the retries — a provider-side cooldown signal, not a failure
    of the row."""


class BodyTooLarge(ProviderUnavailable):
    """Response body exceeded max_bytes — refuse, never half-read."""


def http_get(url, *, timeout=3.0, attempts=3, backoff=2.0,
             max_bytes=MAX_BODY, opener=None, sleep=time.sleep):
    """GET url -> bytes. Retries URLError/429/5xx with exponential backoff
    (backoff * 2**n, VERIFIED red-capable in tests/test_enrich_ol.py); a
    definitive 4xx (not 429) is not retried. Raises RateLimited on a final 429,
    ProviderUnavailable otherwise."""
    # Scheme rule in the MECHANISM, not in each caller: urllib's default opener
    # ships FileHandler/FTPHandler, so an unchecked url turns this function into
    # a local file reader (measured: file:///etc/hostname returned its bytes).
    parts = urlsplit(str(url))
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ProviderUnavailable(f"endast http/https hämtas — nekar {url!r}")
    op = opener or _default_opener()
    last = None
    for attempt in range(attempts):
        try:
            resp = op.open(url, timeout=timeout)
            try:
                body = resp.read(max_bytes + 1)
            finally:
                resp.close()
            if len(body) > max_bytes:
                raise BodyTooLarge(
                    f"svaret är större än {max_bytes} byte — nekas")
            return body
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                if attempt == attempts - 1:
                    raise RateLimited(f"429 from {url}") from e
            elif e.code >= 500:
                if attempt == attempts - 1:
                    raise ProviderUnavailable(f"{e.code} from {url}") from e
            else:
                raise ProviderUnavailable(f"{e.code} from {url}") from e
        except (urllib.error.URLError, OSError) as e:   # DNS, timeout, reset
            last = e
            if attempt == attempts - 1:
                raise ProviderUnavailable(f"transport failed for {url}") from e
        sleep(backoff * (2 ** attempt))
    raise ProviderUnavailable(f"transport failed for {url}: {last}")


def http_get_json(url, **kw):
    """http_get + json.loads; a body that is not JSON is a ProviderUnavailable
    (a WAF page or an HTML error screen must never parse as a hit)."""
    body = http_get(url, **kw)
    try:
        return json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise ProviderUnavailable(f"non-JSON body from {url}") from e


def build_opener():
    op = urllib.request.build_opener()
    op.addheaders = [("User-Agent", USER_AGENT),
                     ("Accept", "application/json, image/*;q=0.8, */*;q=0.5")]
    return op


def _default_opener():
    # Built per call on purpose: a module-level opener would keep connection
    # state across tests that inject their own (the opener= parameter is the
    # single seam every test uses — fixture transport, never the network).
    return build_opener()


# --------------------------------------------------------------------------
# The match policy + provider order + the ONE cover normalizer (T3.4).
# Genre vocabulary and its mapping rules are cycle-1 §5 verbatim, kept here as
# the plan pins them in this file.

MAX_TITLE_SIMILARITY_MIN = 0.80      # difflib ratio floor for a provider hit
MAX_COVER_EDGE = (340, 510)          # §5.11: normalized covers are ≤340×510
COVER_QUALITY = 82
COVER_SUBDIR = "covers"
MANUAL_COVER_SOURCES = ("manual", "manual-url")
# The row's own format -> the provider hit types that fit it (§7 enum 'bok' /
# 'ljudbok'). Libris answers one title as several editions; see prefer_format.
HIT_TYPE_BY_FORMAT = {"bok": ("book", "text"), "ljudbok": ("sound recording",)}
# Owner ruling 2026-11-13, the rule named in full because it is the exception
# that proves the rule beside it: identity is the first matcher's, always.
COVER_COMPLETION = ("cover completion: providers after the identity matcher may "
                    "supply ONLY a cover, never identity fields")
PROVIDER_ORDER = ("libris", "ol", "gb")

# cycle-1 §5 (binding): substring match on lower-cased subject strings, max 3
# labels per book, anything unmatched or no subjects at all → Övrigt.
GENRE_RULES = (
    ("Romantik", ("romanc", "love story", "kärlek")),
    ("Familjesaga", ("family", "släkt", "saga", "generation")),
    ("Kriminalitet", ("crime", "detective", "mord", "polis", "thriller")),
    ("Historisk roman", ("histor", "krig", "world war", "historisk")),
    ("Självbiografiskt", ("biograph", "memoir", "självbiograf")),
    ("Reseskildring", ("travel", "rese", "reportage")),
    ("Natur och vardag", ("nature", "garden", "natur", "trädgård", "mat", "food")),
    ("Samhälle och aktualitet", ("societ", "samhälle", "current affairs")),
)
GENRE_OTHER = "Övrigt"


class CoverRejected(Exception):
    """Bytes that are not a storable image, or a cover URL that is not an
    http(s) image — refuse, never write a broken cover file."""


def normalize_title(text):
    folded = unicodedata.normalize("NFKD", str(text or "").casefold())
    return re.sub(r"[^a-z0-9åäöéèé]+", "", folded)


def title_similarity(a, b):
    return difflib.SequenceMatcher(None, normalize_title(a),
                                   normalize_title(b)).ratio()


def authors_overlap(book_authors, hit_authors):
    """The §T3.4 gate applies only when BOTH sides name an author; then any
    near-equal pair (equal, containment, or ratio ≥ 0.85) opens it."""
    if not book_authors or not hit_authors:
        return True
    for mine in book_authors:
        m = normalize_title(mine)
        for theirs in hit_authors:
            t = normalize_title(theirs)
            if not m or not t:
                continue
            if m == t or m in t or t in m:
                return True
            if difflib.SequenceMatcher(None, m, t).ratio() >= 0.85:
                return True
    return False


def map_genres(subjects):
    """§5 mapping: max 3 labels, else Övrigt (also when there are no
    subjects at all — the plan's own wording, verified Swedish subjects such
    as 'Skönlitteratur' match no rule and therefore land on Övrigt)."""
    found = []
    for label, needles in GENRE_RULES:
        if label in found:
            continue
        for subject in subjects or []:
            low = str(subject).casefold()
            if any(needle in low for needle in needles):
                found.append(label)
                break
    return found[:3] if found else [GENRE_OTHER]


def fetch_cover(url, *, fetch=None, max_bytes=MAX_BODY):
    """Download a candidate cover. Scheme-checked BEFORE any fetch (a provider
    field is data, never a command: file:// and friends are refused outright),
    then size-capped."""
    fetch = fetch or http_get
    if not isinstance(url, str) or not url.lower().startswith(("http://", "https://")):
        raise CoverRejected(f"inte en http(b)-bild: {url!r}")
    data = fetch(url, max_bytes=max_bytes)
    if len(data) > max_bytes:
        raise BodyTooLarge(f"bilden är större än {max_bytes} byte — nekas")
    return data


def store_cover(conn, book_id, data, source):
    """THE cover normalizer (T5.3 upload and T6.4 bundle write reuse THIS):
    Pillow → RGB → thumbnail ≤340×510 → JPEG q82 → <state_base()>/covers/
    <book_id>.jpg, and the row's cover_path/cover_source are written here so
    file and row can never disagree. Bytes that are not an image are refused
    with nothing written."""
    from PIL import Image, UnidentifiedImageError

    from app import db
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, ValueError) as e:
        raise CoverRejected(f"inte en bild: {e}") from e
    img = img.convert("RGB")
    img.thumbnail(MAX_COVER_EDGE)
    rel = f"{COVER_SUBDIR}/{book_id}.jpg"
    target = db.state_base() / COVER_SUBDIR / f"{book_id}.jpg"
    target.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=COVER_QUALITY)
    target.write_bytes(buf.getvalue())

    from app import auth
    conn.execute("UPDATE book SET cover_path = ?, cover_source = ?, updated = ? "
                 "WHERE id = ?", (rel, source, auth.utcnow_iso(), book_id))
    conn.commit()
    return rel


def book_authors(conn, book_id):
    return [r[0] for r in conn.execute(
        "SELECT a.name FROM author a JOIN book_author ba ON ba.author_id = a.id "
        "WHERE ba.book_id = ?", (book_id,))]


def prefer_format(candidates, book_format):
    """Among the hits that PASSED the match policy, the row's own format picks
    the edition. Measured on the recorded Libris page for Stöld: one title
    answers as an analysis booklet, an article, a ljudbok and the book, the
    ljudbok listed first — and taking it for a print row writes an audiobook
    ISBN into the diary. Candidates from a provider that names no type
    (OpenLibrary, Google Books) keep the plan's first-hit order untouched."""
    wanted = HIT_TYPE_BY_FORMAT.get(book_format, ())
    for hit in candidates:
        if str(hit.get("type") or "").lower() in wanted:
            return hit
    for hit in candidates:
        if not hit.get("type"):
            return hit                     # ol/gb answers: order wins as pinned
    return candidates[0]


def resolve_book(conn, book_id, *, transports=None, fetch=None, now=time.time):
    """Enrich ONE row: libris→ol→gb, the first provider whose hit passes the
    match policy (difflib ≥0.80 + the author gate) wins; writes
    isbn13/isbn10/year (holes only), genres (holes only, §5 mapping), the
    cover (never over an admin's own cover, 'manual' or 'manual-url')
    and the F-2 evidence columns.

    Match policy (pinned): similarity >= MAX_TITLE_SIMILARITY_MIN on folded
    titles plus the author gate, applied to EVERY hit of the first provider
    that answers; among its passing hits the row's `format` picks the edition
    (prefer_format). The provider ORDER still wins: a later provider is never
    asked once one has matched.

    Transport contract: a transport returns a LIST (answered), None (not
    consulted — cooldown/down, NOT recorded in tried_providers) or raises
    ProviderUnavailable (consulted and failed — RECORDED). tried_providers is
    the honest attempt log T5.5's `unobtainable` reads; enrich_fail=1 means
    the whole order produced nothing usable (no-match included), which is what
    makes a row VERIFIED-unobtainable rather than merely un-tried.
    Nothing here raises: a failing row is a written row."""
    from app import auth
    row = conn.execute("SELECT id, title, isbn13, year, cover_path, cover_source, "
                       "format FROM book WHERE id = ?", (book_id,)).fetchone()
    if row is None:
        return {"resolved": False, "reason": "no such book"}
    title = row[1]
    authors = book_authors(conn, book_id)
    transports = transports or live_transports(conn, now=now)

    tried, chosen, after = [], None, []
    for name in PROVIDER_ORDER:
        transport = transports.get(name)
        if transport is None:
            continue                       # provider unavailable: no attempt
        try:
            hits = transport(title, authors)
        except ProviderUnavailable:
            tried.append(name)
            continue
        if hits is None:
            continue                       # not consulted (cooldown) — no log
        tried.append(name)
        candidates = [hit for hit in hits
                      if title_similarity(title, hit.get("title")) >= MAX_TITLE_SIMILARITY_MIN
                      and authors_overlap(authors, hit.get("authors"))]
        if candidates:
            chosen = prefer_format(candidates, row[6])
            after = PROVIDER_ORDER[PROVIDER_ORDER.index(name) + 1:]
            break                          # order wins: never ask the next one

    ts = auth.utcnow_iso()
    if chosen is None:
        conn.execute("UPDATE book SET tried_providers = ?, enrich_fail = 1, "
                     "updated = ? WHERE id = ?",
                     (",".join(tried), ts, book_id))
        conn.commit()
        return {"resolved": False, "tried": tried}

    isbn13 = chosen.get("isbn13") or row[2]
    isbn_written = row[2] is None and bool(isbn13)   # a filled hole, not a match
    year = row[3] if row[3] is not None else chosen.get("year")
    genres = map_genres(chosen.get("subjects"))
    # An admin's own cover — uploaded ('manual') or found via hitta-omslag
    # ('manual-url', the OQ-2 ruling) — is never painted over by a provider.
    cover_ok = row[5] not in MANUAL_COVER_SOURCES
    cover_written, cover_from = None, chosen["source"]
    if cover_ok and not chosen.get("cover_url"):
        # COVER_COMPLETION (owner ruling 2026-11-13): the matcher found the
        # work but has no cover to offer (Libris' xsearch page never does), so
        # the providers AFTER it are asked — for a cover only. The same
        # title+author policy gates the cover hit; no identity field is read
        # from it. When the matcher DID have a cover, nothing further is asked.
        if after:
            for name in after:
                transport = transports.get(name)
                if transport is None:
                    continue                       # not consulted, not logged
                try:
                    hits = transport(title, authors)
                except ProviderUnavailable:
                    tried.append(name)
                    continue
                if hits is None:
                    continue
                tried.append(name)
                offering = [hit for hit in hits
                            if hit.get("cover_url")
                            and title_similarity(title, hit.get("title")) >= MAX_TITLE_SIMILARITY_MIN
                            and authors_overlap(authors, hit.get("authors"))]
                if offering:
                    cover_hit = prefer_format(offering, row[6])
                    chosen = dict(chosen, cover_url=cover_hit["cover_url"])
                    # cover_source names the COVER lane, never the identity lane
                    cover_from = cover_hit.get("source") or cover_from
                    break
    if cover_ok and chosen.get("cover_url"):
        try:
            cover_written = store_cover(conn, book_id,
                                        fetch_cover(chosen["cover_url"], fetch=fetch),
                                        cover_from)
        except (ProviderUnavailable, CoverRejected):
            cover_written = None           # a cover failure never loses the isbn

    genres_written = False
    if genres and not _has_genres(conn, book_id):
        _set_genres(conn, book_id, genres)
        genres_written = True

    conn.execute("UPDATE book SET isbn13 = ?, isbn10 = COALESCE(isbn10, ?), "
                 "year = ?, tried_providers = ?, enrich_fail = 0, updated = ? "
                 "WHERE id = ?",
                 (isbn13, chosen.get("isbn10"), year, ",".join(tried), ts, book_id))
    conn.commit()
    return {"resolved": True, "source": chosen["source"], "tried": tried,
            "cover_source": cover_from if cover_written else None,
            "genres": genres, "genres_written": genres_written,
            "isbn_written": isbn_written, "cover": cover_written}


def live_transports(conn, *, now=time.time):
    """The three real providers wrapped to the transport contract above.
    Imported late: enrich is imported by the CLI and the app alike, the client
    modules import enrich back (no cycle)."""
    from app import enrich_gb, enrich_libris, enrich_ol

    def libris(title, authors):
        if not enrich_libris.available(now=now):
            return None                    # DOWN window: not an attempt
        author = authors[0] if authors else ""
        hits = enrich_libris.search(title, author, now=now)
        if hits is None:
            raise ProviderUnavailable("libris transport failed")
        return hits

    def openlibrary(title, authors):
        author = authors[0] if authors else ""
        return enrich_ol.search(title, author)   # raises on transport failure

    def google_books(title, authors):
        if not enrich_gb.available(conn, now=now):
            return None
        author = authors[0] if authors else ""
        hits = enrich_gb.search(title, author, conn, now=now)
        if hits is None:
            raise ProviderUnavailable("google books transport failed")
        return [dict(hit, cover_url=hit.get("thumbnail")) for hit in hits]

    return {"libris": libris, "ol": openlibrary, "gb": google_books}


def _has_genres(conn, book_id):
    return conn.execute("SELECT 1 FROM book_genre WHERE book_id = ?",
                        (book_id,)).fetchone() is not None


def _set_genres(conn, book_id, names):
    for name in names:
        conn.execute("INSERT OR IGNORE INTO genre (name) VALUES (?)", (name,))
        gid = conn.execute("SELECT id FROM genre WHERE name = ?", (name,)).fetchone()[0]
        conn.execute("INSERT OR IGNORE INTO book_genre (book_id, genre_id) VALUES (?, ?)",
                     (book_id, gid))
