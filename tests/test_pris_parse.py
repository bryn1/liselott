"""MC 12547 (M9a-2a) — the PURE pris-parser legs: the five MEASURED classes
over SYNTHETIC html fragments (real sweep DOMs never entered this file; every
fixture isbn is a 979-prefixed synthetic value — instrument-checked, staged
scripts/exposure_check.py exit 0). The runner legs and the card contract
live in tests/test_pris_vakt.py, which imports the fragments defined here —
the repo's own cross-test-fixture idiom (cf. tests/test_pris_door.py
importing tests.test_browse). Planted-red per gate: .tmp/m9a2a-planted-red.md.

Legs: physical-one-price, script-text-excluded, campaign-two-price =>
AMBIGUOUS, format-page => FORMAT (no fallback-to-another-number),
not-found-title => NOT-CARRIED (a planted cart+price behind a bad title is
still NOT-CARRIED — the title tail + /bok/ URL are the ONLY identity gates),
nbsp-token, price-bounds (0 / 20 001 reject, 20 000 with the thousands space
accepts), cart-without-box => NO-PRICE, bytes-in; plus the §2 readers: only
the "Att läsa" section is scope, section_missing / empty_section named, the
legit no_isbn and the isbn_shape alarm.
"""
import re

from scripts import pris_parse as pp


def isbn(n):
    """Synthetic 13-digit isbn, 979-prefixed (the prefix this diary never
    carries — the same instrument-checked rule as test_pris_door)."""
    return f"979{n:010d}"


def scope_html(ids):
    cards = "".join(f'<li class="bok-kort"><a class="bok-lank" '
                    f'href="/liselott/bok/{i}">bok</a></li>' for i in ids)
    return (f'<html><body><section class="grupp"><h2>Att läsa</h2>'
            f'<ul>{cards}</ul></section></body></html>')


def bok_html(isbn13=None):
    dd = (f'<dt>ISBN</dt><dd class="muted">{isbn13}</dd>' if isbn13 else "")
    return (f'<html><body><dl class="uppgifter">{dd}'
            f'<dt>Antal sidor</dt><dd class="muted">320</dd></dl></body></html>')


# --- synthetic fragments, one per MEASURED page variant ---------------------
# (measured shapes of MC 12540: the box div class chain, the NBSP price <p>,
# the not-found title, the zero-cart format page — zero real bytes/titles)
PROD_ONE = """<html><head><title>Palatsbesöket - Anna Snickars - Inbunden | Bokus</title></head>
<body><div class="page"><script>window.data={"pris":"249 kr","cta":"Lägg i varukorg"};</script>
<div class="mt-5 flex flex-col gap-5"><div class="pris"><p><span>99\u00a0kr</span></p></div>
<div class="product-call-to-action--single"><div><button class="knapp">Lägg i varukorg</button></div></div>
</div></div></body></html>"""

PROD_CAMP = PROD_ONE.replace("<span>99\u00a0kr</span>",
                              "<span>99\u00a0kr</span><s><span>249 kr</span></s>")

PROD_FMT = """<html><head><title>Midvintersyskonen - Elsa Snick - Ljudbok | Bokus</title></head>
<body><div class="format-kop">Lyssna direkt 129 kr</div><p>Ingen tryckupplaga.</p></body></html>"""

PROD_NF = """<html><head><title>Sidan kunde inte hittas - Bokus</title></head>
<body><div class="mt-5 flex flex-col gap-5"><p><span>199 kr</span></p>
<div><button>Lägg i varukorg</button></div></div></body></html>"""

PROD_TAIL = PROD_ONE.replace(" - Inbunden | Bokus</title>", " - Inbunden - Bokus</title>")

PROD_NOBOX = """<html><head><title>Tomhyllan - Nils Snick - Inbunden | Bokus</title></head>
<body><div class="cta"><button>Lägg i varukorg</button></div></body></html>"""

PROD_ZERO = PROD_ONE.replace("99\u00a0kr", "0 kr")
PROD_HIGH = PROD_ONE.replace("99\u00a0kr", "20 001 kr")
PROD_MAX = PROD_ONE.replace("99\u00a0kr", "20 000 kr")

FRAG = {"price": PROD_ONE, "camp": PROD_CAMP, "format": PROD_FMT,
        "notfound": PROD_NF, "nobox": PROD_NOBOX, "zero": PROD_ZERO,
        "high": PROD_HIGH, "max": PROD_MAX}
BOKUS_URL = "https://www.bokus.com/bok/"


# --- parser legs ------------------------------------------------------------
def test_physical_one_price_is_the_price():
    assert pp.classify_product(PROD_ONE, BOKUS_URL + isbn(1)) == (pp.PRICE, 99)


def test_script_text_never_parses_as_box_or_leaf():
    """The script in PROD_ONE carries BOTH a second price and the cart
    sentence; a parser that counted it would answer AMBIGUOUS (2 tokens) or
    find a phantom leaf on a script-only page. It answers PRICE on the
    visible box, and FORMAT (no visible leaf) when the visible page has none:
    """
    assert pp.classify_product(PROD_ONE, BOKUS_URL + isbn(1))[1] == 99
    scripty = ("<html><head><title>X | Bokus</title></head><body>"
               "<script>'Lägg i varukorg', 88 kr</script></body></html>")
    assert pp.classify_product(scripty, BOKUS_URL + isbn(2))[0] == pp.FORMAT


def test_campaign_two_prices_is_ambiguous_never_a_price():
    assert pp.classify_product(PROD_CAMP, BOKUS_URL + isbn(3)) == (pp.AMBIGUOUS, None)


def test_format_page_never_scavenges_another_number():
    assert pp.classify_product(PROD_FMT, BOKUS_URL + isbn(4)) == (pp.FORMAT, None)


def test_not_found_title_is_not_carried_despite_planted_cart_and_price():
    assert pp.classify_product(PROD_NF, BOKUS_URL + isbn(5)) == (pp.NOT_CARRIED, None)


def test_identity_gate_is_the_title_tail_pipe():
    assert pp.classify_product(PROD_TAIL, BOKUS_URL + isbn(6)) == (pp.NOT_CARRIED, None)


def test_identity_gate_also_requires_bok_url():
    assert pp.classify_product(PROD_ONE, "https://www.bokus.com/sok?q=x") \
        == (pp.NOT_CARRIED, None)


def test_nbsp_is_normalized_before_tokenizing():
    assert pp.normalize("99\u00a0kr") == "99 kr"
    assert pp.price_tokens("99\u00a0kr") == [99]


def test_price_bound_zero_is_no_price():
    assert pp.classify_product(PROD_ZERO, BOKUS_URL + isbn(7)) == (pp.NO_PRICE, None)


def test_price_bound_20001_is_no_price():
    assert pp.classify_product(PROD_HIGH, BOKUS_URL + isbn(8)) == (pp.NO_PRICE, None)


def test_price_bound_20000_with_thousands_space_is_the_price():
    assert pp.classify_product(PROD_MAX, BOKUS_URL + isbn(9)) == (pp.PRICE, 20000)


def test_cart_without_a_token_box_is_no_price():
    assert pp.classify_product(PROD_NOBOX, BOKUS_URL + isbn(10)) == (pp.NO_PRICE, None)


def test_parser_accepts_bytes():
    assert pp.classify_product(PROD_ONE.encode("utf-8"), BOKUS_URL + isbn(1)) \
        == (pp.PRICE, 99)


def test_scope_reads_only_the_att_lasa_section():
    html = (scope_html(["7"]) +
            '<section class="grupp"><h2>Klart</h2><ul><li class="bok-kort">'
            '<a class="bok-lank" href="/liselott/bok/99">annan</a></li></ul></section>')
    assert pp.read_scope(html) == (["7"], None)


def test_scope_section_missing_is_named():
    assert pp.read_scope("<html><body><section>x</section></body></html>") \
        == ([], "section_missing")


def test_scope_empty_section_is_named():
    html = ('<html><body><section class="grupp"><h2>Att läsa</h2>'
            '<ul></ul></section></body></html>')
    assert pp.read_scope(html) == ([], "empty_section")


def test_isbn_reader_ok():
    assert pp.read_isbn(bok_html(isbn(11))) == (isbn(11), None)


def test_isbn_reader_without_dt_is_the_legit_no_isbn():
    assert pp.read_isbn(bok_html(None)) == (None, None)


def test_isbn_reader_broken_dd_is_isbn_shape():
    assert pp.read_isbn(bok_html("978-91-00")) == (None, "isbn_shape")


