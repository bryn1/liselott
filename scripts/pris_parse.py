"""MC 12547 (M9a-2a) — the PURE pris-parser: page bytes in, class + price out.

No I/O, no clock, no playwright — the runner (scripts/pris_vakt.py) hands this
module what a hydrated page showed (the serialized DOM + the final URL) and
this module answers with ONE of five classes (SWEEP.md RECIPE-DECISION, the
measured shapes; DESIGN-prisbevakning-v2 §3 parse rules + §2 scope contract):

  PRICE        identity OK, cart leaf found, EXACTLY one price token inside
               the first token-bearing ancestor of the leaf, value 1..20000.
  AMBIGUOUS    identity OK, cart leaf, TWO OR MORE tokens in that box — the
               campaign now/was pair (F-8's named expected miss): never a
               posted price, the class is what gets recorded.
  FORMAT       identity OK but NO `Lägg i varukorg` leaf after the hydration
               wait — the e-bok/ljudbok canonical pages (measured 3/3 zero
               cart leaves). A legitimate outcome, never sale data, and no
               fallback-to-another-number path exists beside this rule.
  NOT-CARRIED  identity FAILS — the title tail gate is the only gate (Bokus
               answers HTTP 200 even for "Sidan kunde inte hittas", measured
               2/6 + negative control), so this parser never looks at a
               status code and this module never sees one.
  NO-PRICE     identity OK, cart leaf present, but the buy box yields NO
               usable token (no token-bearing ancestor, or the single token
               is out of the 1..20000 sanity — 0 kr / 20001 kr is the page
               changing under us, never a price to post). This is the ONLY
               unexpected-parse-failure class: the N=3 consecutive stop and
               the 7-day chronic escalator key on it, and on nothing else
               (the 2 permanently-unlisted ISBNs of the measured shelf are
               NOT-CARRIED/FORMAT forever and must never fire either).

The buy-box walk is the measured one (the nearest-P/SECTION rule died with the
old DOM): primary leaf = the deepest element whose visible text is exactly
`Lägg i varukorg`; box = the FIRST ANCESTOR (any tag) whose whitespace-
normalized text carries ≥ 1 price token (measured: div.mt-5.flex.flex-col.
gap-5 carrying exactly the now/was pair). NBSP (99\u00a0kr) is normalized to a
space BEFORE tokenizing. Token regex `([0-9][0-9 ]*)\\s*kr` (thousands-space
digits) per §3 rule 2. Text inside <script>/<style> is never visible text and
never contributes a token or a leaf.

The scope reader is §2's pinned selector contract over the app's OWN public
page: the section whose <h2> is `Att läsa`, the li.bok-kort > a.bok-lank
cards, and dl.uppgifter's <dt>ISBN</dt><dd class="muted"> on the book page.
The three named scope errors (section_missing / empty_section / isbn_shape)
come back as values, never exceptions — the runner turns them into the ALARM.
"""
import re
from html.parser import HTMLParser

CART_TEXT = "Lägg i varukorg"          # the hydration wait + the leaf text
TITLE_TAIL = "| Bokus"                  # §3 rule 3: the title tail is the gate
BOOK_PATH = "/bok/"                     # ... and the final URL lives under it
PRICE_RE = re.compile(r"([0-9][0-9 ]*)\s*kr")   # §3 rule 2, verbatim shape
PRICE_MIN, PRICE_MAX = 1, 20_000        # mirrors app/pris.py's door bounds
                                        # (duplicated data, not a mechanism:
                                        # importing app.pris would drag flask
                                        # into a pure module)

PRICE, AMBIGUOUS, FORMAT, NOT_CARRIED, NO_PRICE = (
    "PRICE", "AMBIGUOUS", "FORMAT", "NOT-CARRIED", "NO-PRICE")

# The scope contract (§2): the wishlist section label is books.WISHLIST_SECTION
# rendered; the card/link classes and the ISBN dl shape are the app's own
# markup (bibliotek.html / bok.html), pinned by §2's selector list.
WISHLIST_HEADING = "Att läsa"
SCOPE_SECTION_CLASS = "grupp"
CARD_CLASS = "bok-kort"
LINK_CLASS = "bok-lank"
ISBN_DT = "ISBN"
ISBN_DD_CLASS = "muted"
BOOK_ID_RE = re.compile(r"/bok/(\d+)$")
ISBN13_RE = re.compile(r"\d{13}")

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
         "meta", "param", "source", "track", "wbr"}
_HIDDEN = ("script", "style")          # never visible text, never a leaf


def normalize(text):
    """NBSP (and every other whitespace run) to ONE plain space, stripped —
    BEFORE tokenizing (measured: the price renders as `99\u00a0kr`)."""
    return re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()


def price_tokens(text):
    """The §3 rule 2 tokens of normalized text, as int values (thousands
    spaces collapse: "20 000 kr" is 20000)."""
    return [int(m.group(1).replace(" ", ""))
            for m in PRICE_RE.finditer(normalize(text))]


def identity_ok(final_url, title):
    """/bok/ under the landing URL AND the title tail is `| Bokus` — the ONLY
    identity gate (measured: not-found answers 200; the rewrite is
    client-side; a status-code branch is FORBIDDEN)."""
    return (BOOK_PATH in (final_url or "")
            and normalize(title or "").endswith(TITLE_TAIL))


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


def _first(root, tag):
    for node in _walk(root):
        if node.tag == tag:
            return node
    return None


def _cart_leaf(root):
    """The primary leaf: the DEEPEST element whose visible text is exactly
    the cart sentence (document order wins ties — RECIPE-DECISION's leaf)."""
    leaf, depth = None, -1
    for node in _walk(root):
        if node.tag is None or node.tag in _HIDDEN:
            continue
        if _text(node) != CART_TEXT:
            continue
        d, p = 0, node.parent
        while p is not None:
            d += 1
            p = p.parent
        if d > depth:
            leaf, depth = node, d
    return leaf


def _first_ancestor_with_token(leaf):
    node = leaf.parent
    while node is not None:
        text = _text(node)
        if PRICE_RE.search(text):
            return text
        node = node.parent
    return None


def classify_product(src, final_url):
    """THE parser entry: (html bytes/str, final URL) -> (class, price|None).
    Order is the contract's: identity FIRST (the 200-page trap), then the
    cart leaf, then the box token count, then the bounds sanity."""
    root = _root(src)
    title = _first(root, "title")
    if not identity_ok(final_url, _text(title) if title else ""):
        return NOT_CARRIED, None
    leaf = _cart_leaf(root)
    if leaf is None:
        return FORMAT, None
    box = _first_ancestor_with_token(leaf)
    if box is None:
        return NO_PRICE, None
    vals = price_tokens(box)
    if len(vals) >= 2:
        return AMBIGUOUS, None            # the named campaign expected-miss
    if len(vals) == 0 or not PRICE_MIN <= vals[0] <= PRICE_MAX:
        return NO_PRICE, None             # out-of-range = the page moved under us
    return PRICE, vals[0]


def read_scope(src):
    """§2 the public "Att läsa" section -> ([book_id str], scope_error|None).
    ids in page order (the shelf renders the wish order — the FIFO carry
    relies on it). A card whose href is not /bok/<digits> simply yields no id;
    zero ids from a present section IS the named empty_section alarm."""
    root = _root(src)
    scope = None
    for node in _walk(root):
        if node.tag == "section" and SCOPE_SECTION_CLASS in _classes(node):
            heading = next((h for h in _walk(node) if h.tag == "h2"), None)
            if heading is not None and _text(heading) == WISHLIST_HEADING:
                scope = node
                break
    if scope is None:
        return [], "section_missing"
    ids = []
    for card in _walk(scope):
        if card.tag != "li" or CARD_CLASS not in _classes(card):
            continue
        for link in _walk(card):
            if link.tag != "a" or LINK_CLASS not in _classes(link):
                continue
            found = BOOK_ID_RE.search(link.attrs.get("href") or "")
            if found:
                ids.append(found.group(1))
    if not ids:
        return [], "empty_section"
    return ids, None


def read_isbn(src):
    """§2 the book page's dl.uppgifter -> (isbn|None, scope_error|None).
    No ISBN dt at all is the LEGITIMATE no_isbn (a (None, None) answer); a dt
    whose muted dd is not 13 ASCII digits means OUR OWN markup changed —
    that is the named isbn_shape alarm, not a parse nuisance."""
    root = _root(src)
    dl = None
    for node in _walk(root):
        if node.tag == "dl" and "uppgifter" in _classes(node):
            dl = node
            break
    if dl is None:
        return None, None
    kids = dl.kids
    for i, dt in enumerate(kids):
        if dt.tag != "dt" or _text(dt) != ISBN_DT:
            continue
        for dd in kids[i + 1:]:
            if dd.tag == "dt":
                break
            if dd.tag == "dd" and ISBN_DD_CLASS in _classes(dd):
                text = _text(dd)
                if ISBN13_RE.fullmatch(text):
                    return text, None
                return None, "isbn_shape"
        return None, "isbn_shape"
    return None, None
