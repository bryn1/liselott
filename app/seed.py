"""Seed import core (§5) — ONE mechanism shared by the CLI (data-import/
import_seed.py) and the later HTTP routes. Section parsing per §5.1; the
file's header prose (lines 1-7) is parsed nowhere — it carries stale claims
(P2-8), this module's rules are canonical."""
import re
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
