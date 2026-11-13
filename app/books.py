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
NO_AUTHOR = "Okänd författare"
NO_DATE = "Utan läsdatum"
NO_YEAR = "Utan år"               # one trailing group for yearless read rows
WISHLIST_SECTION = "Att läsa"     # §9: the wishlist section's own name
_DATE_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})")


def load_books(conn, ids=None):
    """Every book (or just `ids`) as one dict each: the row's own fields plus
    `authors`/`genres` name lists and a `has_cover` flag. Returned in id
    order — presentation order is sort_by_read_date's job.

    The two vocabularies arrive in two queries total (not one per card: a
    700-card page would otherwise be 1 400 queries)."""
    sql = ("SELECT id, title, year, read_year, date_read, rating, format,"
           " status, isbn13, isbn10, cover_path, notes FROM book")
    params = ()
    if ids is not None:
        if not ids:
            return []
        placeholders = ", ".join("?" for _ in ids)
        sql += f" WHERE id IN ({placeholders})"
        params = tuple(ids)
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


def group_for_shelf(books):
    """[(label, rows)] for the shelf: ONE section per read_year, the years
    newest first; read rows without a usable year (the seed's 0 sentinel)
    form ONE trailing "Utan år" group; the wishlist is the §9 section
    "Att läsa" LAST; within a group the sort_by_read_date order stands.

    Keyed on the read_year VALUE, never run-length over the sorted rows:
    most corpus rows carry no date_read, so the sorted block runs in title
    order and its years jump on nearly every row — run-length opened a new
    section at each jump (F-A: 583 headings over 12 real years). `status`,
    never the year, decides the read/wish split (a wish row's 0 is its
    sentinel, not a year)."""
    read = sort_by_read_date([b for b in books if b["status"] == "read"])
    wishlist = sort_by_read_date([b for b in books if b["status"] != "read"])
    by_year = {}
    utan_ar = []
    for book in read:
        try:                                   # F-A2 (b, MC 12451): a DB
            year = int(book["read_year"])      # written before the write-
        except (TypeError, ValueError,         # door fix CAN carry a TEXT
                OverflowError):                # year — ONE guarded int
            year = 0                           # conversion so sorted() can
                                               # never compare str against
                                               # int (the shelf-brick 500)
        if year:
            by_year.setdefault(year, []).append(book)
        else:
            utan_ar.append(book)
    groups = [(year, by_year[year])
              for year in sorted(by_year, reverse=True)]
    if utan_ar:
        groups.append((NO_YEAR, utan_ar))
    if wishlist:
        groups.append((WISHLIST_SECTION, wishlist))
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
