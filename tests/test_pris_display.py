"""MC 12542 (M9a-1) — the price line on the card, as the page renders it
(DESIGN-prisbevakning-v2 §5 + the owner's public-scope ruling of 2026-11-15,
verbatim: "every graded book displayed, every book on whishlist displayed,
current price and a 'on sale' if on sale for vooks on whishlist").

What is public here is a DISPLAY, not a door: the price and the REA ride the
wishlist cards an anonymous reader already sees, through the ONE `bokkort`
macro; nothing on the card buys, carts or reserves, and the deep-link is
derived by the SERVER from the stored isbn (§1) — never a client URL.

The legs are the three render cases §5 names, on the anonymous page, plus the
absence proofs that keep the promise small:

  sale     → price + "REA" + the pinned subtitle + the worded check date
  stale    → the price, its worded date and the honest "kan ha ändrats" — and
             NO badge (§4 rule 1: a day nothing was observed cannot badge)
  no price → NO element at all: no dashes, no empty chrome, no "–" (§5: "No
             observation ⇒ no markup"), and the page carries exactly as many
             price lines as there are priced wishes

  + the read-year cards carry no price line even when a price row exists for
    that isbn (the map is built from the wishlist only) — the shelf's other
    sections render the bytes they rendered before prices existed;
  + /onska (the owner) makes the SAME macro call, so her rows carry the same
    line: one mechanism, no second one;
  + the link's exact shape: https://www.bokus.com/bok/<isbn13>, no query, no
    affiliate or tracking param, and no "?price=" anywhere on the page.

The series is POSTed through the door (`pris.ingest`), one day per day, with
its own day as the door's clock — the same code the HTTP door runs. Only THIS
file uses a today-anchored clock, because the anonymous page renders against
the real one: `NU` is today at 09:00 UTC, so the freshness test's "today" and
the view's "today" are the same calendar day wherever the suite runs.

Honest limit, stated rather than hidden: the page renders against the real
clock, so these legs are anchored to today's UTC DATE. A run that crossed UTC
midnight between posting the series and rendering the page would see the
series age by a day and the fresh legs go red — rerun the file, the code is
right. Nothing in the app guesses a date to hide that.

PLANTED-RED, one per gate the display added (transcripts on MC 12542's trail,
every one red on its own leg first): the badge block ungated
(`{% if pris.rea %}` → `{% if pris %}`, red on the stale leg — an outage would
have shouted REA), the stale marker ungated (`{% if pris.stale %}` → false,
red on the same leg's "kan ha ändrats"), the whole price block ungated
(`{%- if pris %}` → true, red on the two no-observation legs at once — the
dashes-chrome §5 forbids, rendered), the read rows let into the read's isbn
scope (red on the query-count leg: the price table got read at all) and the
map's read filter dropped (red on the shared-isbn leg, where a read twin
carrying the wish's isbn took the line).
"""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app import books, create_app, db, pris, priskort
from tests.test_browse import PASSWORD, seed_shelf
from tests.test_pris_door import WISH_ISBN, row

NU = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0,
                                        microsecond=0)
DJUP = [100] * 8 + [95]                 # 8 days of a floor, then a new low
LINK = "https://www.bokus.com/bok/" + WISH_ISBN


def serien(conn, *prices, fran_slut=0):
    """The prices, one day each, the LAST one landing `fran_slut` days back
    from today — each POSTed with its own day as the door's clock."""
    dagar = len(prices)
    for i, price in enumerate(prices):
        dag = NU - timedelta(days=dagar - 1 - i + fran_slut)
        pris.ingest(conn, [row(price=price, when=dag)], now=dag)


def app_pa(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    with sqlite3.connect(tmp_path / "liselott.db") as c:
        c.execute("UPDATE book SET isbn13 = ? WHERE id = 5", (WISH_ISBN,))
    app = create_app()
    app.testing = True
    return app


@pytest.fixture()
def publikt(tmp_path, monkeypatch):
    """The CONFIGURED site — anonymous reader, owner client, and the open
    connection the price series is written through."""
    app = app_pa(tmp_path, monkeypatch)
    anon = app.test_client()
    owner = app.test_client()
    assert owner.post("/liselott/satt-loesenord",
                      data={"loesenord": PASSWORD,
                            "bekrafta": PASSWORD}).status_code == 302
    with app.app_context():
        yield anon, owner, db.get_db()


@pytest.fixture()
def tomt(tmp_path, monkeypatch):
    """The same site with NO price table content at all — the calm page."""
    app = app_pa(tmp_path, monkeypatch)
    sätt = app.test_client()          # the setup POST signs THAT client in —
    assert sätt.post("/liselott/satt-loesenord",                        # so the
                     data={"loesenord": PASSWORD,
                           "bekrafta": PASSWORD}).status_code == 302     # reader
    anon = app.test_client()                                             # below is
    with app.app_context():                                              # genuinely
        yield anon, db.get_db()                                          # anonymous


# ── the sale case, anonymous ────────────────────────────────────────────────
def test_a_wish_on_sale_shows_its_price_and_the_badge_to_anyone(publikt):
    anon, _, conn = publikt
    serien(conn, *DJUP)
    body = anon.get("/liselott/bibliotek").text
    assert "95 kr · Bokus" in body
    assert ">REA<" in body
    assert "tätat pris (90 d)" in body          # §5's pinned subtitle, verbatim
    assert "pris kollat " in body               # the check date is REQUIRED
    assert books.sw_date(NU.date().isoformat()) in body   # …sw_date's own words


def test_the_deep_link_is_the_servers_not_the_pages(publikt):
    """§1: the public link is `https://www.bokus.com/bok/` ‖ isbn — built by
    the server from the stored isbn. A stored or client-supplied URL is the
    hole the design closed by DELETING the column, and this leg is where a
    query string would sneak back in."""
    anon, _, conn = publikt
    serien(conn, *DJUP)
    body = anon.get("/liselott/bibliotek").text
    assert f'<a class="pris-lank" href="{LINK}">' in body
    förbjudet = ("?price", "?ref", "?affiliate", "?utm", "?src",
                 "bokus.com/checkout")
    for ord in förbjudet:
        assert ord not in body, ord


def test_the_price_line_is_a_link_out_never_a_purchase(publikt):
    """§5's money line: the price is a DISPLAY. No form, no button, no cart
    word appears anywhere the price line appears."""
    anon, _, conn = publikt
    serien(conn, *DJUP)
    rad = anon.get("/liselott/bibliotek").text
    prisrad = rad[rad.index("prisrad"):rad.index("</li>", rad.index("prisrad"))]
    for ord in ("<form", "<button", "Lägg i", "kundvagn", "Köp", "beställ"):
        assert ord.lower() not in prisrad.lower(), ord


# ── the stale case ──────────────────────────────────────────────────────────
def test_a_price_not_seen_today_shows_as_stale_and_never_badges(publikt):
    """§5's outage posture: the runner stops, the price does not vanish, and
    the card says honestly when it was last seen — while §4 rule 1 keeps the
    badge off a day nothing was observed."""
    anon, _, conn = publikt
    serien(conn, *DJUP, fran_slut=1)            # the series STOPPED yesterday
    body = anon.get("/liselott/bibliotek").text
    assert "95 kr · Bokus" in body
    assert ("pris kollat "
            + books.sw_date((NU - timedelta(days=1)).date().isoformat())
            + " — kan ha ändrats") in body
    assert ">REA<" not in body
    assert "prisrad" in body


# ── the no-observation case, and the byte-identity of everything else ───────
def test_a_wish_without_prices_renders_the_card_it_always_rendered(tomt):
    """§5: "No observation ⇒ no markup". Not an empty <p>, not a dash — the
    element is not there, so the page is byte-what-it-was for that card."""
    anon, conn = tomt
    body = anon.get("/liselott/bibliotek").text
    assert "prisrad" not in body and " kr · Bokus" not in body
    assert "En skatt av silver" in body          # the wish IS on the page
    serien(conn, *DJUP)                          # …and now it has a price
    pricead = anon.get("/liselott/bibliotek").text
    assert pricead.count('class="prisrad"') == 1  # the one wish that has data
    assert ">REA<" in pricead


def test_only_the_wishlist_section_carries_a_price_line(publikt):
    """§5: the year sections are NOT passed price data — their cards go on
    rendering the bytes they rendered before prices existed. Here a price row
    for a READ book's isbn (inserted by hand: the door refuses it, which is
    test_pris_door's leg) proves the filter is the view's, not the data's."""
    anon, _, conn = publikt
    serien(conn, *DJUP)
    with conn:
        conn.execute("INSERT INTO price (isbn, book_id, retailer, price,"
                     " checked_at) VALUES (?,2,'bokus',120,?)",
                     ("9789173710015", NU.strftime("%Y-%m-%dT%H:%M:%SZ")))
    body = anon.get("/liselott/bibliotek").text
    fore_las, att_lasa = body.split(">Att läsa</h2>")   # the section, not a nav word
    assert "prisrad" not in fore_las
    assert "prisrad" in att_lasa
    assert "120 kr" not in body                 # the read book's price is invisible
    assert body.count('class="prisrad"') == 1   # …and it never doubled up


def test_the_owner_wishlist_rows_carry_the_same_line_from_the_same_macro(publikt):
    """§5's "ONE macro call, zero second mechanism": /onska renders the same
    card with the same price map, so the owner sees what a visitor sees."""
    _, owner, conn = publikt
    serien(conn, *DJUP)
    body = owner.get("/liselott/onska").text
    assert "95 kr · Bokus" in body and ">REA<" in body
    assert f'href="{LINK}"' in body
    assert "tätat pris (90 d)" in body


def test_the_duplicate_wish_400_page_carries_the_price_too(publikt):
    """/onska has THREE states (the list, a validation error, a duplicate) and
    all three are ONE render (`_onska`) — so the duplicate's 400 page carries
    the price map too, and the wish that HAS a series still shows it there.

    This leg exists because a first cut of the card routed two of the three
    states through `_onska` and left the duplicate branch a hand-written
    `render_template` WITHOUT `prisar`: the suite caught it as a
    jinja2.UndefinedError on 'prisar' (tests/test_wishlist.py's double-wish
    leg), which is the right outcome for a template that names a variable its
    view forgot — but the contract belongs pinned here, not left to a crash in
    someone else's file."""
    _, owner, conn = publikt
    serien(conn, *DJUP)                        # the seeded wish now has a price
    from tests.test_wishlist import token
    data = {"titel": "Dubbel önskan", "forfattare": "Dubbel",
            "csrf": token(owner)}
    assert owner.post("/liselott/onska/lagg-till", data=data).status_code == 302
    svar = owner.post("/liselott/onska/lagg-till", data=data)
    assert svar.status_code == 400
    body = svar.get_data(as_text=True)         # the price line rides the 400
    assert "Den boken står redan på önskelistan." in body
    assert "95 kr · Bokus" in body and f'href="{LINK}"' in body


def test_the_search_page_passes_no_price_and_stays_the_same_page(publikt):
    """§5: the search page never gets price data. (The door to /sok is the
    owner's — MC 12501 put search back behind the password — so this leg runs
    logged in, which is the only way the page renders at all.)"""
    _, owner, conn = publikt
    serien(conn, *DJUP)
    body = owner.get("/liselott/sok?q=skatt").text
    assert "En skatt av silver" in body
    assert "prisrad" not in body and " kr · Bokus" not in body


def test_a_read_book_sharing_a_wishs_isbn_gets_no_price_line(publikt):
    """§5's scope at its sharpest: a READ row and a WISH carrying the SAME
    isbn — the series belongs to the BOOK (§1 says so outright), so the read
    card could have taken the line and must not. The map is built from the
    cards it was handed, MINUS every read row: the year sections keep the
    bytes they had before prices existed and the price appears exactly once,
    on the wish."""
    anon, _, conn = publikt
    with conn:
        conn.execute("UPDATE book SET isbn13 = ? WHERE id = 2", (WISH_ISBN,))
    serien(conn, *DJUP)
    body = anon.get("/liselott/bibliotek").text
    fore_las, att_lasa = body.split(">Att läsa</h2>")
    assert "Nattfjärden" in fore_las                 # the read twin IS on the page
    assert "prisrad" not in fore_las
    assert body.count('class="prisrad"') == 1
    assert "95 kr · Bokus" in att_lasa


# ── the one read, and what it hands the template ────────────────────────────
def test_one_query_answers_the_whole_page(publikt):
    """§1's "one read, never two", measured on the connection: the composed
    map costs EXACTLY one SELECT over the price table for a page of three
    priced wishes — and a shelf of nothing but read rows does not touch the
    table AT ALL (the read is scoped to the wishlist's isbns before it is
    issued). A per-card query is the N+1 the design forbids, and a trace
    callback is the only honest way to SEE the difference."""
    anon, _, conn = publikt
    serien(conn, *DJUP)
    with conn:
        for bok, isbn in ((6, "9789173710114"), (7, "9789173710121")):
            conn.execute("INSERT INTO book (id, title, format, read_year,"
                         " status, book_key, created, updated)"
                         " VALUES (?,'Flersidig',?,0,'wishlist',?,"
                         " '2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')",
                         (bok, "bok", f"key-{bok}"))
            conn.execute("UPDATE book SET isbn13 = ? WHERE id = ?", (isbn, bok))
    serien(conn, 120, fran_slut=0)              # the two new wishes get a price
    antal = []
    conn.set_trace_callback(
        lambda sql: "FROM price" in sql and antal.append(sql[:60]))
    svar = priskort.card_prices(conn, books.load_books(conn))
    assert len(antal) == 1, antal               # one statement, three wishes
    assert len(svar) == 1                       # …of which ONE carries a series
    antal.clear()
    larta = [b for b in books.load_books(conn) if b["status"] == "read"]
    assert priskort.card_prices(conn, larta) == {}
    assert antal == [], antal                   # the price table is never read
    conn.set_trace_callback(None)


def test_the_map_is_built_from_the_cards_it_is_handed(publikt):
    """The engine has no opinion about which books exist: hand it the shelf's
    rows and it answers the wishlist's ids, nothing else — which is what lets
    the shelf and /onska share one mechanism."""
    _, _, conn = publikt
    serien(conn, *DJUP)
    alla = books.load_books(conn)
    priser = priskort.card_prices(conn, alla)
    assert list(priser) == [5]
    assert priskort.card_prices(conn, [b for b in alla if b["id"] != 5]) == {}
