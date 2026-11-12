"""Seed import core (§5) — ONE mechanism shared by the CLI (data-import/
import_seed.py) and the later HTTP routes. Section parsing per §5.1; the
file's header prose (lines 1-7) is parsed nowhere — it carries stale claims
(P2-8), this module's rules are canonical."""
import csv
import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

# ## Lästa böcker YYYY | ## Lyssnade böcker YYYY | ## Lyssnat på böcker YYYY
# "(N st)" labels may be stale — parser counts are canonical, labels are read
# nowhere. ## Att läsa ... -> wishlist (read_year 0 sentinel).
_SECTION_RE = re.compile(
    r"^## (Lästa böcker|Lyssnade böcker|Lyssnat på böcker) (\d{4})")
_WISHLIST_PREFIX = "## Att läsa"

KIND_BY_HEADER = {
    "Lästa böcker": "läst",
    "Lyssnade böcker": "lyssnad",
    "Lyssnat på böcker": "lyssnad",
}

# §5.3 strip rules (run on the WHOLE row BEFORE the author split — F-6/P2-2/P2-6):
# (a) trailing "(betyg N i källan)" -> rating; (b) ANY parenthetical containing
# "i källan" wherever it sits; (c) exact leading "(utan datum)"; (d) other
# parentheticals stay in the title.
_RATING_RE = re.compile(r"\(betyg ([1-5]) i källan\)\s*$")
_KALLAN_RE = re.compile(r"\((?:[^()]*i källan[^()]*)\)")
_DATE_RE = re.compile(r"^(\d{6})\s+")
# Author split: text after the LAST literal " av " (case-sensitive). Census
# (PLAN-c3 §2): exactly 4 rows carry " av " inside the title — FIRST-split
# corrupts them; LAST-split is correct for all. " af " (L723) never matches.
_AV_SEP = " av "
# §5.4 validator: the literal split cannot see tab-form separators; a tail
# that still carries an av-separator (any whitespace form) is routed to the
# overrides handling instead of corrupting the row.
_AV_TAIL_RE = re.compile(r"\s+av\s+")
# §5.4 author name splitting: " och ", ", ", " & "; " – " only when the next
# token starts UPPERCASE (co-author), lowercase keeps the subtitle.
_AUTHOR_SPLIT_RE = re.compile(r"\s+och\s+|\s*,\s+|\s+&\s+")
_DASH_RE = re.compile(r"\s+–\s+")


def parse_row(row: str) -> dict:
    """One raw row -> {date_read, title, authors, rating, bad_author_tail}."""
    text = row.strip()

    rating = None
    m = _RATING_RE.search(text)
    if m:
        rating = int(m.group(1))
        text = _RATING_RE.sub("", text).strip()
    text = _KALLAN_RE.sub(" ", text)
    if text.startswith("(utan datum)"):
        text = text[len("(utan datum)"):].lstrip()

    date_read = None
    m = _DATE_RE.match(text)
    if m and 15 <= int(m.group(1)[:2]) <= 26:
        yy, mm, dd = m.group(1)[:2], m.group(1)[2:4], m.group(1)[4:6]
        date_read = f"20{yy}-{mm}-{dd}"
        text = text[m.end():]

    idx = text.rfind(_AV_SEP)
    if idx == -1:
        title, tail = text, ""
    else:
        title, tail = text[:idx], text[idx + len(_AV_SEP):]
    # §5.4 validator on the RAW tail (a whitespace collapse here would hide
    # tab-form separators from the flag).
    flagged = bool(_AV_TAIL_RE.search(tail))
    title = re.sub(r"\s+", " ", title).strip()
    tail = re.sub(r"\s+", " ", tail).strip()

    authors = []
    if tail:
        for part in _AUTHOR_SPLIT_RE.split(tail):
            part = part.strip()
            if not part:
                continue
            pieces = _DASH_RE.split(part)
            authors.append(pieces[0])
            for nxt in pieces[1:]:
                nxt = nxt.strip()
                if nxt and nxt[0].isupper():
                    authors.append(nxt)
                elif authors:
                    authors[-1] = f"{authors[-1]} – {nxt}"

    return {"date_read": date_read, "title": title, "authors": authors,
            "rating": rating, "bad_author_tail": flagged}


def load_aliases(path) -> dict:
    """data-import/author_aliases.csv: 'canonical,alias' rows -> alias→canonical."""
    with Path(path).open(encoding="utf-8") as fh:
        return {alias: canonical for canonical, alias in csv.reader(fh)}


def register_author(conn, name: str, aliases: dict) -> int:
    """Upsert the ALIAS-RESOLVED canonical author; an alias also lands in
    author_alias (§5.5). Unknown names pass through unchanged."""
    canonical = aliases.get(name, name)
    conn.execute("INSERT OR IGNORE INTO author (name) VALUES (?)", (canonical,))
    author_id = conn.execute(
        "SELECT id FROM author WHERE name = ?", (canonical,)).fetchone()[0]
    if canonical != name:
        conn.execute(
            "INSERT OR IGNORE INTO author_alias (alias, author_id) VALUES (?, ?)",
            (name, author_id))
    return author_id


# §5.3 book_key: the ONE bundle-upsert match key (P1-3). NFD+casefold+strip
# normalization; authors sorted AFTER normalization, so input order cannot
# drift the key. Computed by seed insert, export_bundle and add-book alike.
def _norm(s: str) -> str:
    return unicodedata.normalize("NFD", s).casefold().strip()


def book_key(title: str, authors) -> str:
    joined = "\x1f".join(sorted(_norm(a) for a in authors))
    return hashlib.sha256(f"{_norm(title)}\x1f{joined}".encode()).hexdigest()


# §5.7 dedupe key: NFD, lowercased, diacritics stripped, non-alnum -> one space
# + sorted canonical author list.
def _fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s).lower()
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def read_overrides(path) -> dict:
    """import_overrides.csv: 'exact title,date' rows (applied after parsing,
    before dedupe, §5.6)."""
    out = {}
    p = Path(path)
    if p.is_file():
        with p.open(encoding="utf-8") as fh:
            for title, date in csv.reader(fh):
                out[title.strip()] = date.strip()
    return out


def _merge_pair(records: list[dict]) -> dict:
    """§5.7 tie-break: date_read = MAX non-NULL (both NULL -> NULL), read_year
    = MAX, note marks the re-read."""
    keeper = dict(records[0])
    dates = [r["date_read"] for r in records if r["date_read"]]
    keeper["date_read"] = max(dates) if dates else None
    keeper["read_year"] = max(r["read_year"] for r in records)
    note = "läst igen (omläsning)"
    keeper["notes"] = f"{keeper['notes']} {note}".strip() if keeper.get("notes") else note
    return keeper


def dedupe_read(records: list[dict]):
    """read+read duplicates on the §5.7 fold key (and rows colliding on
    book_key) collapse to ONE row; wishlist rows pass through untouched."""
    groups: dict[tuple, list[dict]] = {}
    order: list[tuple] = []
    survivors, pairs = [], []
    for r in records:
        if r["status"] != "read":
            survivors.append(r)
            continue
        k = (_fold(r["title"]), tuple(sorted(r["canon_authors"])))
        if k not in groups:
            order.append(k)
        groups.setdefault(k, []).append(r)
    merged = []
    for k in order:
        g = groups[k]
        if len(g) == 1:
            merged.append(g[0])
        else:
            merged.append(_merge_pair(g))
            pairs.append({"title": g[0]["title"],
                          "read_years": [r["read_year"] for r in g]})
    # Second pass: different fold keys but identical book_key share the path.
    by_key: dict[str, list[dict]] = {}
    key_order: list[str] = []
    for r in merged:
        if r["book_key"] not in by_key:
            key_order.append(r["book_key"])
        by_key.setdefault(r["book_key"], []).append(r)
    for k in key_order:
        g = by_key[k]
        if len(g) == 1:
            survivors.append(g[0])
        else:
            survivors.append(_merge_pair(g))
            pairs.append({"title": g[0]["title"],
                          "read_years": [r["read_year"] for r in g],
                          "reason": "book_key collision"})
    return survivors, pairs


def load(conn, raw_path, aliases_path, overrides_path) -> dict:
    """Parse the raw seed md and store books+authors per §5. Idempotent:
    re-importing the same rows updates nothing new (book_key UNIQUE)."""
    aliases = load_aliases(aliases_path)
    overrides = read_overrides(overrides_path)
    entries = parse_file(raw_path)
    flagged: list[str] = []
    records: list[dict] = []
    for e in entries:
        row = parse_row(e["raw"])
        if row["bad_author_tail"]:
            flagged.append(row["title"])  # §5.4 -> overrides handling, never corrupt
            continue
        if row["title"] in overrides:
            row["date_read"] = overrides[row["title"]]
        canon = [aliases.get(a, a) for a in row["authors"]]
        records.append({**row, "canon_authors": canon,
                        "format": e["format"], "status": e["status"],
                        "read_year": e["year"], "notes": None,
                        "book_key": book_key(row["title"], canon)})
    survivors, pairs = dedupe_read(records)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for r in survivors:
        # register under the RAW names so alias spellings populate
        # author_alias; the returned ids are always the canonical ones.
        author_ids = [register_author(conn, a, aliases) for a in r["authors"]]
        cur = conn.execute(
            "INSERT OR IGNORE INTO book (title, format, date_read, read_year,"
            " rating, notes, status, book_key, created, updated)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (r["title"], r["format"], r["date_read"], r["read_year"],
             r["rating"], r["notes"], r["status"], r["book_key"], now, now))
        book_id = (cur.lastrowid if cur.rowcount
                   else conn.execute("SELECT id FROM book WHERE book_key = ?",
                                     (r["book_key"],)).fetchone()[0])
        for aid in set(author_ids):
            conn.execute("INSERT OR IGNORE INTO book_author (book_id, author_id)"
                         " VALUES (?,?)", (book_id, aid))
    conn.commit()

    def q(sql):
        return conn.execute(sql).fetchone()[0]

    return {"parsed": len(entries), "stored": q("SELECT COUNT(*) FROM book"),
            "duplicates": len(pairs), "duplicates_pairs": pairs,
            "ratings": q("SELECT COUNT(*) FROM book WHERE rating IS NOT NULL"),
            "ljudbok": q("SELECT COUNT(*) FROM book WHERE format='ljudbok'"),
            "flagged": flagged}


def parse_file(path) -> list[dict]:
    """Raw seed md -> list of entry dicts (kind, year, format, status, raw).

    Only '- ' bullets INSIDE a known section are entries; everything before
    the first '## ' header, '### ' sub-headers and blank lines carry no data.
    """
    text = Path(path).read_text(encoding="utf-8")
    entries: list[dict] = []
    section = None  # (kind, year, format, status) or None before the first header
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.startswith("## "):
            m = _SECTION_RE.match(line)
            if m:
                kind = KIND_BY_HEADER[m.group(1)]
                fmt = "ljudbok" if kind == "lyssnad" else "bok"
                section = (kind, int(m.group(2)), fmt, "read")
            elif line.startswith(_WISHLIST_PREFIX):
                section = ("wishlist", 0, "bok", "wishlist")
            else:
                raise ValueError(f"seed line {lineno}: unknown section {line!r}")
            continue
        if section is None or not line.startswith("- "):
            continue  # header region, ### sub-headers and blanks: parsed nowhere
        entries.append({"kind": section[0], "year": section[1],
                        "format": section[2], "status": section[3],
                        "raw": line[2:]})
    return entries
