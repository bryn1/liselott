"""Shared text handling (§7's fold). Its own file because BOTH halves of the
product need it: app.search matches with it, app.books orders with it, and any
third place must import it rather than re-derive å≈a."""
import re
import unicodedata


def fold(text) -> str:
    """Case-fold + diacritic-fold, whitespace runs collapsed.

    NFKD first, then the combining marks are dropped, then casefold: 'Å',
    'Å', 'å' and 'a' all land on 'a', so one fold applied to both sides of a
    comparison IS §7's "match raw too" (the accented and unaccented spelling
    of what she typed end up as the same string)."""
    decomposed = unicodedata.normalize("NFKD", str(text or ""))
    stripped = "".join(c for c in decomposed
                       if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", stripped.casefold()).strip()
