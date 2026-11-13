"""T6.1 — the recommendation engine (§8; the formula is cycle-1 §8 verbatim):

    score(c) = 0.55 · max_{a ∈ c.authors} A(a)
             + 0.35 · avg_{g ∈ c.genres} G(g)
             + 0.10 · is_wishlist(c)

Candidate universe: wishlist books ∪ candidate-table rows, minus anything
with status='read' (a book she has read is not a suggestion) and minus
anything dismissed — `dismissed.key` is 'book:<id>' for a wish and
'cand:<id>' for a pool row (P2-3: both kinds are dismissible, both kinds are
excluded here).

A(a)/G(g) are her own ratings normalised to [0,1] (sum / (5 · n)); an author
or genre with no rated book scores 0 — the pinned seams: an empty-genre
candidate's avg lane is 0 (avg over the empty set := 0, never a division),
and a candidate author joins to the canonical author THROUGH author_alias,
an unresolvable name simply has A=0 (a dead candidate, not a crash).

Ties: author name, then title — plain string compare, so the order is stable
and the test can pin it exactly. No I/O, no Flask: pure SQL+python over a
connection, which is what makes the hand-computed fixture possible.
"""
A_WEIGHT = 0.55
G_WEIGHT = 0.35
WISHLIST_BONUS = 0.10

AUTHOR_REASON = "För att du gav ”{title}” {rating} i betyg av {author}"
GENRE_REASON = "För att du gillar {genre}"


def _author_scores(conn):
    """author id -> A(a) over her rated books (Σ rating / (5·n)); unrated
    authors are absent (= 0)."""
    return {row[0]: row[1] / (5.0 * row[2]) for row in conn.execute(
        "SELECT ba.author_id, SUM(b.rating), COUNT(*) FROM book b"
        " JOIN book_author ba ON ba.book_id = b.id"
        " WHERE b.rating IS NOT NULL GROUP BY ba.author_id")}


def _genre_scores(conn):
    """genre name -> G(g); unrated genres absent (= 0)."""
    return {row[0]: row[1] / (5.0 * row[2]) for row in conn.execute(
        "SELECT g.name, SUM(b.rating), COUNT(*) FROM book b"
        " JOIN book_genre bg ON bg.book_id = b.id"
        " JOIN genre g ON g.id = bg.genre_id"
        " WHERE b.rating IS NOT NULL GROUP BY g.name")}


def _author_ids(conn):
    """name -> id for every author, alias spellings included — the seam's
    join path (candidate.author_name is stored canonical, but an older or
    foreign row carrying an alias must still reach the canonical id)."""
    ids = {name: author_id for author_id, name in conn.execute(
        "SELECT id, name FROM author")}
    for alias, author_id in conn.execute(
            "SELECT alias, author_id FROM author_alias"):
        ids.setdefault(alias, author_id)
    return ids


def _author_names(conn):
    """id -> canonical name — the reason line names the CANONICAL author even
    when the candidate row carries an alias spelling (the §8 seam)."""
    return {author_id: name for author_id, name in conn.execute(
        "SELECT id, name FROM author")}


def _reason_book(conn, author_id, a_scores):
    """The author's highest-RATED book; rating ties break on newer
    date_read, NULL dates lose (NULLs last). None when she has rated
    nothing by this author (A=0 — there is no rated book to name)."""
    if not a_scores.get(author_id):
        return None
    return conn.execute(
        "SELECT title, rating FROM book b"
        " JOIN book_author ba ON ba.book_id = b.id"
        " WHERE ba.author_id = ? AND b.rating IS NOT NULL"
        " ORDER BY b.rating DESC, (b.date_read IS NULL),"
        "          b.date_read DESC LIMIT 1", (author_id,)).fetchone()


def _book_items(conn, dismissed):
    for book_id, title, year in conn.execute(
            "SELECT id, title, year FROM book WHERE status = 'wishlist'"):
        if f"book:{book_id}" in dismissed:
            continue
        authors = [name for (name,) in conn.execute(
            "SELECT a.name FROM author a JOIN book_author ba"
            " ON ba.author_id = a.id WHERE ba.book_id = ? ORDER BY a.name",
            (book_id,))]
        genres = [name for (name,) in conn.execute(
            "SELECT g.name FROM genre g JOIN book_genre bg"
            " ON bg.genre_id = g.id WHERE bg.book_id = ? ORDER BY g.name",
            (book_id,))]
        yield {"kind": "book", "id": book_id, "title": title, "year": year,
               "authors": authors, "genres": genres, "is_wishlist": True}


def _cand_items(conn, dismissed):
    for cand_id, title, author_name, year in conn.execute(
            "SELECT id, title, author_name, year FROM candidate"):
        if f"cand:{cand_id}" in dismissed:
            continue
        yield {"kind": "cand", "id": cand_id, "title": title, "year": year,
               "authors": [author_name] if author_name else [],
               "genres": [],                      # the table carries none
               "is_wishlist": False}


def _score(item, a_scores, g_scores, author_ids):
    a_values = [a_scores[author_ids[name]]
                for name in item["authors"]
                if name in author_ids and author_ids[name] in a_scores]
    g_values = [g_scores.get(name, 0.0) for name in item["genres"]]
    a = max(a_values) if a_values else 0.0
    g = sum(g_values) / len(g_values) if g_values else 0.0   # empty set := 0
    bonus = WISHLIST_BONUS if item["is_wishlist"] else 0.0
    return A_WEIGHT * a + G_WEIGHT * g + bonus


def _reason(conn, item, a_scores, g_scores, author_ids, author_names):
    """Author reason first — it explains the dominant lane: the contributing
    author (max A, tie on name) and HER highest-rated book. No author signal
    but a genre she rated → the §8 genre line (max G, tie on name). Neither
    (the t=0 state) → no reason line at all; the page shows the empty-state
    copy instead."""
    contributing = [(a_scores[author_ids[name]], name)
                    for name in item["authors"]
                    if name in author_ids and a_scores.get(author_ids[name])]
    if contributing:
        # max A, tie on the alphabetically first name — same tie policy as
        # the list sort: deterministic, explainable, no float luck.
        best = sorted(contributing, key=lambda an: (-an[0], an[1]))[0]
        author_id = author_ids[best[1]]
        book = _reason_book(conn, author_id, a_scores)
        if book:
            return AUTHOR_REASON.format(
                title=book[0], rating=book[1],
                author=author_names.get(author_id, best[1]))
    rated_genres = [(g_scores[name], name) for name in item["genres"]
                    if g_scores.get(name)]
    if rated_genres:
        return GENRE_REASON.format(
            genre=sorted(rated_genres, key=lambda gn: (-gn[0], gn[1]))[0][1])
    return None


def _tie_name(item):
    """The tie-break author: a candidate carries exactly one name; a book's
    is its first (sorted) name so a multi-author wish has one deterministic
    key."""
    return item["authors"][0] if item["authors"] else ""


def top_recommendations(conn, n=12):
    """The top-n list, best first. Each item: kind/id/title/year/authors/
    genres/score/reason — 'book' is a wishlist row, 'cand' a pool row (the
    data-kind the UI and the T8.8 acceptance leg read)."""
    dismissed = {key for (key,) in conn.execute("SELECT key FROM dismissed")}
    a_scores, g_scores = _author_scores(conn), _genre_scores(conn)
    author_ids, author_names = _author_ids(conn), _author_names(conn)
    items = list(_book_items(conn, dismissed))
    items += list(_cand_items(conn, dismissed))
    for item in items:
        item["score"] = _score(item, a_scores, g_scores, author_ids)
        item["reason"] = _reason(conn, item, a_scores, g_scores, author_ids,
                                 author_names)
    items.sort(key=lambda i: (-i["score"], _tie_name(i), i["title"]))
    return items[:n]
