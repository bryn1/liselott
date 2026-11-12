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
