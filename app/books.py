"""The read model behind the pages (§7's ordering, §9's copy voice).

ONE loader for the whole book record (row + canonical author names + genre
names), ONE sort, ONE grouping, and the Swedish formatters. app.search
imports the same loader and the same sort — browse and search must never
disagree about what a book is or in what order it appears."""
import re

from app.text import fold

MONTHS_SV = ("januari", "februari", "mars", "april", "maj", "juni", "juli",
             "augusti", "september", "oktober", "november", "december")
FORMAT_WORDS = {"bok": "Bok", "ljudbok": "Ljudbok"}
# MC 12733 (M12 W1, R1 + DA-verdict-w1 F1 fix round): the two new statuses
# display through Swedish words — the stored tokens stay English (the
# read/wishlist precedent; FORMAT_WORDS is the house mechanism). STATUS_WORDS
# is the ONE display map AND its own consumer: group_for_shelf reads its
# section labels THROUGH it (the original wave shipped the words twice — the
# constants beside an unconsumed map — that was F1; the duplicate constants
# are retired here, the map is the single source). The F-E ruling rules that
# no status word ever paints in anonymous bytes (filtrering and the grouping
# carry the posture; the public shelf labels a rated-aborted or rated-reading
# row by its year, never by its status). The bok.html action-row buttons are
# §9's fixed ACTION copy (verbs, not status words), pinned in the same leg.
NO_AUTHOR = "Okänd författare"
NO_DATE = "Utan läsdatum"
NO_YEAR = "Utan år"               # one trailing group for yearless read rows
STATUS_WORDS = {"read": "Läst", "wishlist": "Att läsa",   # §9: wish section
                "reading": "Läser nu",                    # owner shelf FIRST
                "aborted": "Avbruten"}                    # before "Att läsa"
_DATE_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})")

# MC 12501 (owner ruling 2026-11-14, verbatim): "Rated books and their
# ratings as well as whishlist shall be public. The rest behind password" —
# the ONE definition of the PUBLIC SET, and since MC 12733 an ENUMERATION:
# a row whose rating is real (rating IS NOT NULL — any status; a rated
# "Avbruten" row is public AS A PLAIN CARD, the F-E ruling) or a wish row
# (`status = 'wishlist'`). The pre-W1 wide form `status <> 'read'` is
# RETIRED: once 'reading'/'aborted' exist it would publish every unread row
# (a läser nu book on the public shelf — exactly the hole F-A/F-E name).
# The read/wish split is `status`, exactly the one group_for_shelf draws
# (never the read_year 0 sentinel: yearless READ rows carry it too and
# belong to the private half when unrated). load_books applies it when a
# caller asks for `public_only`; routes.cover composes the SAME predicate
# into its own row probe — one rule, no second gate beside it.
PUBLIC_SET_SQL = "(rating IS NOT NULL OR status = 'wishlist')"


def load_books(conn, ids=None, public_only=False):
    """Every book (or just `ids`) as one dict each: the row's own fields plus
    `authors`/`genres` name lists and a `has_cover` flag. Returned in id
    order — presentation order is sort_by_read_date's job.

    `public_only` narrows the fetch to PUBLIC_SET_SQL AND strips the note
    field (F-1 cure, MC 12501) — the anonymous read posture. The owner's
    reads never pass it: her view is the full shelf, notes included,
    unchanged.

    F-1 (SEC-verdict-12501; owner ruling 2026-11-14): the ruling named the
    rated books, their ratings and the wishlist public — the free-text note
    is NOT named, so it is "the rest behind password". The public
    projection therefore carries NO notes value: the SELECT itself yields
    NULL for it, so no template — today's bok.html render or a future one —
    can paint an anonymous note. One gate, at the data layer; the templates
    add no second one. The date_read ("Läst") stays public by design: it
    rides the rated-book card the ruling made public.

    The two vocabularies arrive in two queries total (not one per card: a
    700-card page would otherwise be 1 400 queries)."""
    notes_sql = "NULL" if public_only else "notes"
    sql = ("SELECT id, title, year, read_year, date_read, rating, format,"
           f" status, isbn13, isbn10, cover_path, {notes_sql} AS notes"
           " FROM book")
    clauses = []
    params = ()
    if ids is not None:
        if not ids:
            return []
        clauses.append(f"id IN ({', '.join('?' for _ in ids)})")
        params = tuple(ids)
    if public_only:
        clauses.append(PUBLIC_SET_SQL)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    books = {row[0]: {
        "id": row[0], "title": row[1], "year": row[2], "read_year": row[3],
        "date_read": row[4], "rating": row[5], "format": row[6],
        "status": row[7], "isbn13": row[8], "isbn10": row[9],
        "has_cover": row[10] is not None, "notes": row[11],
        "authors": [], "genres": [],
    } for row in conn.execute(sql, params)}

    for row in conn.execute(
            "SELECT ba.book_id, a.name FROM book_author ba"
            " JOIN author a ON a.id = ba.author_id ORDER BY a.name"):
        book = books.get(row[0])
        if book is not None:
            book["authors"].append(row[1])
    for row in conn.execute(
            "SELECT bg.book_id, g.name FROM book_genre bg"
            " JOIN genre g ON g.id = bg.genre_id ORDER BY g.name"):
        book = books.get(row[0])
        if book is not None:
            book["genres"].append(row[1])
    return list(books.values())


def sort_by_read_date(books):
    """§7: date_read desc, NULLs last, title as the stable tie-break. ISO
    dates sort lexically == chronologically, and "" (a NULL) lands last under
    reverse=True — two plain stable sorts, no key gymnastics."""
    ordered = sorted(books, key=lambda b: fold(b["title"]))
    ordered.sort(key=lambda b: b["date_read"] or "", reverse=True)
    return ordered


def shelf_year(book) -> int:
    """The shelf's OWN year for a row — the read_year the section heading
    shows — through the ONE guarded int conversion (F-A2 (b, MC 12451): a DB
    written before the write-door fix CAN carry a TEXT year, so one guard
    keeps sorted() from comparing str against int — the shelf-brick 500).
    0 is the yearless sentinel; a wish row's 0 rides along too, which is why
    the read/wish split is on `status`, never on this value."""
    try:
        return int(book["read_year"])
    except (TypeError, ValueError, OverflowError):
        return 0


def shelf_month(book) -> int:
    """MC 12733 (M12 W1) — the month a row was read, through the SAME guarded
    posture shelf_year teaches the year: ONE reader of the ONE date format
    (_DATE_RE, sw_date's own), and everything the row does not truthfully
    carry — no date, a malformed one, an impossible month — is 0, the same
    sentinel "no usable value" means everywhere here. Born for the Året page
    (W2); guarded from its first line, because sort/sum keys must never be
    the place a stored string first gets parsed."""
    match = _DATE_RE.match(book["date_read"]) if book["date_read"] else None
    if not match:
        return 0
    month = int(match.group(2))
    return month if 1 <= month <= 12 else 0


def group_for_shelf(books, owner_view=False):
    """[(label, rows)] for the shelf: ONE section per read_year, the years
    newest first; read rows without a usable year (the seed's 0 sentinel)
    form ONE trailing "Utan år" group; the wishlist is the §9 section
    "Att läsa" LAST; within a group the sort_by_read_date order stands.

    MC 12733 (M12 W1) adds the OWNER's posture, carried by ONE flag from the
    ONE view point (routes._hylldata): `owner_view=True` puts the two new
    statuses in their own sections — "Läser nu" FIRST, "Avbruten" after
    "Utan år" and before "Att läsa" — and an empty new section never renders
    (the _hyllan law). The DEFAULT is the public posture, ruled in the same
    commit (F-E): it paints NO status word — a non-wishlist row is a PLAIN
    row grouped by its shelf year (only a RATED aborted row can ever reach a
    public reader, and it rides as the plain card MC 12501 made public).

    Keyed on the read_year VALUE, never run-length over the sorted rows:
    most corpus rows carry no date_read, so the sorted block runs in title
    order and its years jump on nearly every row — run-length opened a new
    section at each jump (F-A: 583 headings over 12 real years). `status`,
    never the year, decides the read/wish split, and the wish test is the
    ONE wish law `== 'wishlist'` (F-A), never the wide `!= 'read'`."""
    wishlist = sort_by_read_date([b for b in books if b["status"] == "wishlist"])
    if owner_view:
        reading = sort_by_read_date([b for b in books if b["status"] == "reading"])
        avbrutna = sort_by_read_date([b for b in books if b["status"] == "aborted"])
        plain = [b for b in books if b["status"] == "read"]
    else:
        reading = avbrutna = []
        # F-E ruling: every non-wish row is plain here — only a RATED row can
        # be public at all (PUBLIC_SET_SQL), and it faces the shelf as a card.
        plain = [b for b in books if b["status"] != "wishlist"]
    read = sort_by_read_date(plain)
    by_year = {}
    utan_ar = []
    for book in read:
        year = shelf_year(book)                # F-A2's guarded int, ONE place
        if year:
            by_year.setdefault(year, []).append(book)
        else:
            utan_ar.append(book)
    groups = [(year, by_year[year])
              for year in sorted(by_year, reverse=True)]
    if utan_ar:
        groups.append((NO_YEAR, utan_ar))
    if reading:
        groups.insert(0, (STATUS_WORDS["reading"], reading))
    if avbrutna:
        groups.append((STATUS_WORDS["aborted"], avbrutna))
    if wishlist:
        groups.append((STATUS_WORDS["wishlist"], wishlist))
    return groups


def sw_date(date_read):
    """'2026-10-29' -> '29 oktober 2026'; a missing date is NAMED (the row
    says she read it without a date), never filled in with today."""
    if not date_read:
        return NO_DATE
    match = _DATE_RE.match(date_read)
    if not match:
        return date_read
    year, month, day = (int(g) for g in match.groups())
    if not 1 <= month <= 12:
        return date_read
    return f"{day} {MONTHS_SV[month - 1]} {year}"


def authors_text(book):
    """Canonical author names; an author-less row says so instead of printing
    a dangling separator."""
    if not book["authors"]:
        return NO_AUTHOR
    if len(book["authors"]) == 1:
        return book["authors"][0]
    return ", ".join(book["authors"][:-1]) + " och " + book["authors"][-1]


def year_text(book):
    return str(book["year"]) if book["year"] else "Okänt år"


def format_word(book):
    return FORMAT_WORDS.get(book["format"], book["format"])
