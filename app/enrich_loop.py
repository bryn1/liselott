"""The loop core shared by every door that walks enrichment (P2-d's one
mechanism, §8): ONE pacing courtesy (1 req/s, §12), ONE budget wrapper, and —
from T5.6 — the one scope/cursor selection. scripts/enrich_backfill.py (the
CLI) and app/backfill.py (the route) both run THESE functions, not twins.

The budget rule is deliberately honest: a provider the budget stopped is NOT
consulted, so it answers None (= "not asked"), the exact posture a cooldown
has since T3 — never an error, and never recorded in tried_providers. An
honest attempt log beats a full-looking one."""

PACE_S = 1.0                       # §12: 1 req/s against the providers


def with_budget(transports, budget_s, *, sleep, clock):
    """1 PACE_S pause before every CONSULTED provider call; past the budget the
    provider answers None (not consulted — the cooldown posture, NOT recorded
    in tried_providers). sleep/clock are parameters so the 6 s budget is
    testable without a wall clock (see test_add's budget leg)."""
    start = clock()
    wrapped = {}
    for name, transport in transports.items():
        if transport is None:
            wrapped[name] = None
            continue

        def call(title, authors, _t=transport):
            if clock() - start + PACE_S > budget_s:
                return None
            sleep(PACE_S)
            return _t(title, authors)

        wrapped[name] = call
    return wrapped


def paced(transports, pace):
    """1 req/s wrapped around every CONSULTED provider call (a transport the
    caller skips with None is not asked, so it never costs a pause). Moved
    verbatim from scripts/enrich_backfill.py when the app's own doors became
    its second caller — the CLI imports THIS, so there is no twin."""
    wrapped = {}
    for name, transport in transports.items():
        if transport is None:
            wrapped[name] = None
            continue

        def call(title, authors, _t=transport):
            pace(PACE_S)
            return _t(title, authors)

        wrapped[name] = call
    return wrapped


def paced_fetch(fetch, pace):
    """A cover image is an outbound request too — the 1 req/s courtesy covers
    it, not just the search calls. (Moved with paced; same reason.)"""
    def call(url, **kw):
        pace(PACE_S)
        return fetch(url, **kw)

    return call


SCOPE_WHERE = "isbn13 IS NULL OR cover_path IS NULL"


def scope_ids(conn, limit=None, after=0):
    """The PINNED scope and cursor (P2-d): rows still carrying a hole, id >
    after, ORDER BY id, LIMIT n. Rows that failed PERMANENTLY (enrich_fail=1)
    stay IN scope — they are examined and last_id advances past them, so the
    scan completes and never spins on poisoned ground. THE selection for the
    CLI AND the POST /backfill route — one mechanism."""
    sql = (f"SELECT id FROM book WHERE ({SCOPE_WHERE})"
           " AND id > ? ORDER BY id")   # parens: AND outranks OR
    params = [after]
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    return [r[0] for r in conn.execute(sql, params)]


def run_pass(conn, ids, transports, fetch, pace, persist=True):
    # Moved VERBATIM from scripts/enrich_backfill.py when the route became its
    # second caller (P2-d: the route runs over the SAME pipeline as the CLI).
    # isbn_resolved counts isbn13 values WRITTEN (the DoD's floor metric: what
    # the diary GAINED), matched counts provider hits that passed the policy —
    # conflating them made a re-run report "54 resolved" while writing nothing.
    report = {"scanned": 0, "processed": 0, "matched": 0, "isbn_resolved": 0,
              "covers_stored": 0, "genres_set": 0, "failures": 0, "writes": 0,
              # per-lane attribution (owner ruling 2026-11-13): a missed floor
              # must name which provider missed it
              "by_source": {lane: {"matched": 0, "isbn": 0, "covers": 0,
                                   "genres": 0}
                            for lane in ("libris", "openlibrary",
                                         "googlebooks")}}
    from app import enrich
    for book_id in ids:
        report["scanned"] += 1
        outcome = enrich.resolve_book(conn, book_id, transports=transports,
                                      fetch=fetch)
        report["processed"] += 1
        if not outcome.get("resolved"):
            report["failures"] += 1
            continue
        report["matched"] += 1
        lane = report["by_source"].setdefault(
            outcome.get("source") or "unknown",
            {"matched": 0, "isbn": 0, "covers": 0, "genres": 0})
        lane["matched"] += 1
        # a cover supplied under COVER_COMPLETION belongs to the lane that
        # supplied the BYTES, not the lane that identified the work
        cover_lane = report["by_source"].setdefault(
            outcome.get("cover_source") or outcome.get("source") or "unknown",
            {"matched": 0, "isbn": 0, "covers": 0, "genres": 0})
        if outcome.get("isbn_written"):
            report["isbn_resolved"] += 1
            lane["isbn"] += 1
        if outcome.get("cover"):
            report["covers_stored"] += 1
            cover_lane["covers"] += 1
        if outcome.get("genres_written"):
            report["genres_set"] += 1
            lane["genres"] += 1
        if persist:
            report["writes"] += 1
    return report


def author_queue(conn, limit=None, after=0):
    """The candidates-mode queue (§8): the authors OF THE DIARY — authors of
    books she marked read — id > after ORDER BY id LIMIT n. The same pinned
    cursor contract as scope_ids, over author ids instead of book ids."""
    sql = ("SELECT DISTINCT a.id, a.name FROM author a"
           " JOIN book_author ba ON ba.author_id = a.id"
           " JOIN book b ON b.id = ba.book_id AND b.status = 'read'"
           " WHERE a.id > ? ORDER BY a.id")
    params = [after]
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    return list(conn.execute(sql, params))


def candidates_pass(conn, authors, search, *, now, stale_before, aliases=None):
    """THE candidate builder — T5.6's route and T6.3's CLI both run THIS.
    Per author: skip the FETCH while a fresh (< stale_before window) candidate
    of her already sits in the pool (the 90-day refresh rule); otherwise ask
    `search(name)` and insert hits that are new to the pool: a title already
    owned by a BOOK never enters at all, and the candidate dedupe key is
    (canonical author, folded title) — two authors writing the same title is
    real life, the same author+title twice is not. author_name is stored
    CANONICAL through the alias chain (T1.4's mechanism at INSERT).

    KNOWN LIMITATION stated honestly (T6.3 owns the fuller builder): freshness
    matches the canonical queue-author name, so an author whose books are
    credited to a PEN NAME re-asks (idempotent — the dedupe key keeps the pool
    stable, it only costs the ask)."""
    from app import text
    aliases = aliases or {}
    report = {"scanned": 0, "processed": 0, "fetched": 0, "new_candidates": 0}
    for author_id, name in authors:
        report["scanned"] += 1
        report["processed"] += 1
        canonical = aliases.get(name, name)
        fresh = conn.execute(
            "SELECT 1 FROM candidate WHERE author_name = ?"
            " AND fetched_at > ? LIMIT 1", (canonical, stale_before)).fetchone()
        if fresh:
            continue
        report["fetched"] += 1
        book_titles = {text.fold(t) for (t,) in conn.execute(
            "SELECT title FROM book")}
        pool = {(text.fold(a), text.fold(t)) for a, t in conn.execute(
            "SELECT author_name, title FROM candidate")}
        for hit in search(name) or []:
            title = (hit.get("title") or "").strip()
            author = ((hit.get("authors") or [None])[0] or canonical)
            author = aliases.get(author, author)
            key = (text.fold(author), text.fold(title))
            if (not title or text.fold(title) in book_titles
                    or key in pool):
                continue
            pool.add(key)
            conn.execute(
                "INSERT INTO candidate (title, author_name, isbn13, year,"
                " fetched_at) VALUES (?,?,?,?,?)",
                (title, author, hit.get("isbn13"), hit.get("year"), now))
            report["new_candidates"] += 1
    conn.commit()
    return report
