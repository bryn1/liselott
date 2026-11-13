"""Provider plumbing for enrichment — the ORCHESTRATION half (§10, F-1:
enrichment runs where the plan says it runs — the VM350 build passes AND the
app's own clients inside its jail): resolve_book walks the provider order
libris→ol→gb under the match policy, and live_transports wraps the three real
clients to the transport contract. The two halves it delegates to split out
of this file in the M4 clean-code pass (§9 seam of
.audits/20261112-phase2): app.enrich_http (the ONE http mechanism) and
app.enrich_match / app.enrich_cover (match policy, genre mapping, the cover
normalizer). This module re-exports every name that moved, so `from app
import enrich` keeps the exact import surface the providers, omslag, the
backfill CLI and the 195-test suite were built against — the split moved
code, not seams."""
import time

# Re-export surface — the names every existing importer reaches through
# app.enrich (omslag, enrich_ol, enrich_libris, enrich_gb,
# scripts/enrich_backfill, tests). Bound here once, from their new homes.
from app.enrich_cover import (COVER_QUALITY, COVER_SUBDIR, MAX_COVER_EDGE,
                              MIN_COVER_PX, CoverRejected, fetch_cover,
                              store_cover)
from app.enrich_http import (MAX_BODY, USER_AGENT, BodyTooLarge,
                             ProviderUnavailable, RateLimited, build_opener,
                             http_get, http_get_json)
from app.enrich_match import (GENRE_OTHER, GENRE_RULES, HIT_TYPE_BY_FORMAT,
                              MAX_TITLE_SIMILARITY_MIN, authors_overlap,
                              map_genres, normalize_title, prefer_format,
                              title_similarity)

# An admin's own cover — uploaded ('manual') or found via hitta-omslag
# ('manual-url', the OQ-2 ruling) — is never painted over by a provider.
MANUAL_COVER_SOURCES = ("manual", "manual-url")
# Owner ruling 2026-11-13, the rule named in full because it is the exception
# that proves the rule beside it: identity is the first matcher's, always.
COVER_COMPLETION = ("cover completion: providers after the identity matcher may "
                    "supply ONLY a cover, never identity fields")
PROVIDER_ORDER = ("libris", "ol", "gb")


def book_authors(conn, book_id):
    return [r[0] for r in conn.execute(
        "SELECT a.name FROM author a JOIN book_author ba ON ba.author_id = a.id "
        "WHERE ba.book_id = ?", (book_id,))]


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
