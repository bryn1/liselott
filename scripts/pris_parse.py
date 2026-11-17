"""The shelf-page reader: the app's OWN public /bibliotek bytes in, the
GRADED cards out (title, author, rating) — the taste profile the /ai-rek
runner builds its prompt from.

MC 12606 (M11-N4b) kept this file and cut it to its one live caller:
`scripts/ai_rek_pass.py::read_library` (the dead_code.py citation for the
keep — the module is REACHED from the live runner; the price/sale feature it
was named for is gone, the reader that outlived it is not). The retired name
stays rather than being renamed here: a rename moves the import site and its
test legs for zero behaviour, and that is its own hygiene row, not a
retirement's.

What the retirement deleted (owner rulings 2026-11-16, verbatim: "Books on
sale can be removed. No interest in buying books." and "rea, om inte nu så
sen"): the Bokus buy-box classifier — the five measured classes (PRICE,
AMBIGUOUS, FORMAT, NOT-CARRIED, NO-PRICE), the price-token walk, the title-
tail identity gate — plus the §2 wishlist-scope and ISBN readers. Every one
of them was driven ONLY by `scripts/pris_vakt.py`, the nightly pris runner
this commit deletes; with the runner gone they had ZERO callers, and a parser
whose page-fetcher no longer exists is capability that does not run. Its
measured shapes live on in the LEDGER rows of MC 12547/MC 12549 and in git.

The graded contract (§5.11's PUBLIC SET read through the ONE markup): the
card is `_bokkort.html`'s `li.bok-kort`, the title/author are its own
classes, and the rating's single source is the star row's accessible label
from `_stjarnor.html` — "Betyg N av 5". Counting the ★ glyphs would parse the
decoration, not the data. Pure: no I/O, no clock.
"""
import re
from html.parser import HTMLParser

# The graded-shelf contract: the classes are the app's own markup.
CARD_CLASS = "bok-kort"
TITEL_CLASS = "titel"
FORFATTARE_CLASS = "forfattare"
STJARNA_CLASS = "stjarnor"
BETYG_RE = re.compile(r"Betyg ([1-5]) av 5")

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
         "meta", "param", "source", "track", "wbr"}
_HIDDEN = ("script", "style")          # never visible text, never a leaf


def normalize(text):
    """Every whitespace run — NBSP included — to ONE plain space, stripped
    (the served pages carry `&nbsp;` inside the visible text)."""
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


class _Node:
    __slots__ = ("tag", "attrs", "kids", "data", "parent")

    def __init__(self, tag, attrs=()):
        self.tag = tag
        self.attrs = dict(attrs)
        self.kids = []
        self.data = []
        self.parent = None


class _Builder(HTMLParser):
    """A parent-linked tree just deep enough for text + ancestors + classes.
    The input is browser-serialized (well-nested), but an end tag still pops
    to its own opener rather than derailing the stack."""

    def __init__(self):
        super().__init__(convert_charrefs=True)   # &nbsp; arrives as \xa0
        self.root = _Node(None)
        self._stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, attrs)
        node.parent = self._stack[-1]
        self._stack[-1].kids.append(node)
        if tag not in _VOID:
            self._stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = _Node(tag, attrs)
        node.parent = self._stack[-1]
        self._stack[-1].kids.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                return

    def handle_data(self, data):
        if self._stack[-1].tag in _HIDDEN:
            return                                # invisible text never parses
        self._stack[-1].data.append(data)


def _root(src):
    builder = _Builder()
    builder.feed(src.decode("utf-8", "replace") if isinstance(src, bytes) else src)
    builder.close()
    return builder.root


def _walk(node):
    yield node
    for kid in node.kids:
        yield from _walk(kid)


def _text(node):
    return normalize("".join(part for n in _walk(node) for part in n.data))


def _classes(node):
    return (node.attrs.get("class") or "").split()


def read_graded(src):
    """Every GRADED card on the served shelf page, in page order:
    [{"title", "author", "rating"}, …]. A card with no star label is NOT a
    graded book (the wishlist's rows and any unrated row ride the page too) —
    dropped here, never carried as a rating of zero: pure, no I/O."""
    root = _root(src)
    cards = []
    for card in _walk(root):
        if card.tag != "li" or CARD_CLASS not in _classes(card):
            continue
        betyg = None
        titel = forfattare = ""
        for node in _walk(card):
            if node.tag == "span" and STJARNA_CLASS in _classes(node):
                found = BETYG_RE.search(node.attrs.get("aria-label") or "")
                if found:
                    betyg = int(found.group(1))
            elif node.tag == "span" and TITEL_CLASS in _classes(node):
                titel = _text(node)
            elif node.tag == "p" and FORFATTARE_CLASS in _classes(node):
                forfattare = _text(node)
        if betyg is None or not titel:
            continue
        cards.append({"title": titel, "author": forfattare, "rating": betyg})
    return cards
