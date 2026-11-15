"""M9a-1 — the price a wishlist card shows (§1 read + §4 badge + §5 display).

ONE read query, ONE evaluator, no second computation of "current price": per
isbn the CURRENT row is MAX(checked_at) (§1), the badge is §4's FLOOR-EVENT
identity, and the view gets a map {book_id: card row} it hands to the ONE
`bokkort` macro (`_hyllan.html`, `/onska`) — one query for the whole page,
never per-card SQL.

§4's rules, as this file reads them (the printed contract, not improvisation):

1. FRESH      — the card badges only on a day the series was actually seen;
                a price whose date ≠ today (UTC) renders AS STALE and can
                never badge (§5: "during the outage the cards show the last
                stored price with its worded date — stale, visibly").
2. DEPTH      — ≥ PRICE_MIN_POINTS distinct earlier calendar days inside
                PRICE_WINDOW_DAYS, each with an observation. Read literally
                ("an observation", not "an accepted observation"): depth says
                the series has thickness; rule 3 is what pins the floor's
                quality, and it names suspect = 0 explicitly.
3. FLOOR      — MIN(price) over the window rows with suspect = 0 ONLY. A
                G1-suspect row enters NO floor (the false-PREVENITION leg: a
                ghost 9 read off a 99 must not silence tomorrow's real REA).
4. G1         — today's own row must be suspect = 0 (the door computes it).
5. MONOTONIC  — enforced at the door (§4 rule 5), never re-derived here.
6. FLOOR EVENT — a badge is ONE EVENT, not one observation: it OPENS on the
                first day the rules hold with price < that day's FLOOR (that
                FLOOR becomes the EVENT FLOOR), PERSISTS while a later
                accepted price stays below the EVENT FLOOR (the same event —
                never a second badge), CLOSES on the first accepted price at
                or above it, and the floor RE-ARMS from the confirmed low.
                The walk below replays that over the window rows at display
                time: nothing is stored about events, so the badge is
                derived truth or nothing.

The event is walked, not memoised, because §4 pins the badge as a property of
the SERIES. On the day an event closes the card shows NO badge (the close IS
that day's verdict) — and it cannot open a new one the same day: the price
that closed it sits at or above the EVENT FLOOR, which is itself inside every
later FLOOR, so the re-armed comparison can only answer "not below".
"""
from datetime import datetime, timedelta, timezone


PRICE_WINDOW_DAYS = 90            # §4: tuning is M9b, the constant cites §4
PRICE_MIN_POINTS = 8              # §4: 8 of the ≈30 observations M9a fetches/mo
BOKUS_BOK_URL = "https://www.bokus.com/bok/"   # §1: server-derived, never stored


def _badge(days):
    """§4 rule 6 as the walk the printed contract derives. `days` is one
    isbn's window rows, oldest first, as (day, price, suspect) — the day is
    unique per isbn (ux_price_isbn_day), so one point per calendar day, and
    every day already walked is strictly earlier than the one being judged.
    Returns True when the badge stands on the series' last day."""
    event_floor = None          # the open event's FIXED floor; None = no event
    lit = False
    alla = []                   # every day walked — rule 2 counts OBSERVATIONS
    earlier = []                # ACCEPTED prices walked so far: the floor's source
    for day, price, suspect in days:
        if suspect:
            alla.append(day)
            continue            # enters no floor, consumes no event (§4 rule 3/6)
        if event_floor is not None:
            lit = price < event_floor        # PERSISTS, or CLOSES right here
            if not lit:
                event_floor = None           # the floor re-arms from the low
        elif len(alla) < PRICE_MIN_POINTS:
            lit = False                      # rule 2: the series is too thin yet
        elif not earlier:
            lit = False                      # no accepted point ⇒ no floor
        elif price < min(earlier):
            event_floor, lit = min(earlier), True   # OPENS, exactly once
        else:
            lit = False                      # rule 3: equal is NOT below
        alla.append(day)
        earlier.append(price)
    return lit


def _utvardera(rows, today, window_start):
    """One isbn's rows (day, price, suspect, checked_at) → that card's price
    row. The window cut happens HERE, not in the SQL: the CURRENT row must
    survive the cut even when it is older than 90 days (§5: a stale price
    renders AS stale, it does not vanish). Rules 1 and 4 are today's own
    verdicts and are applied on top of the walk; rule 2 belongs to the walk
    (its last day is today), so no rule is computed twice."""
    rows = sorted(rows, key=lambda r: r[3])              # checked_at ascending
    day, price, suspect, checked_at = rows[-1]           # MAX(checked_at) = CURRENT
    window = [(d, p, s) for d, p, s, _ in rows if d >= window_start]
    fresh = day == today
    return {
        "price": price,
        "checked_at": checked_at,
        "checked_date": day,
        "stale": not fresh,                 # §5: derived, never stored
        "rea": bool(fresh and not suspect and _badge(window)),
        "isbn": None,           # filled by the caller, which knows the key
        "url": None,
    }


def card_prices(conn, bocker, now=None):
    """{book_id: card row} for the WISHLIST cards in `bocker` — the cards
    §5's ruling puts a price on. Read rows and year-section cards are never in
    the map (the shelf's cards keep rendering exactly the markup they always
    did), and a wish whose isbn has no price row is not in it either: no
    observation is the calm page, never a dash-chrome.

    ONE query for the page (all window rows of the wishes' isbns, plus each
    isbn's CURRENT row even when it sits outside the window), then the
    evaluation in Python — §1's "never two computations of current price".
    `now` is a parameter for the reason §3 gives its timeouts: the two-leg
    §8 series is a property of a day, and a test must be able to name the day.
    """
    today = (now or datetime.now(timezone.utc)).date()
    isbns = sorted({b["isbn13"] for b in bocker
                    if b["status"] != "read" and b["isbn13"]})
    if not isbns:
        return {}
    marks = ", ".join("?" for _ in isbns)
    window_start = (today - timedelta(days=PRICE_WINDOW_DAYS)).isoformat()
    series = {}
    for isbn, price, checked_at, suspect in conn.execute(
            f"SELECT isbn, price, checked_at, suspect FROM price"
            f" WHERE isbn IN ({marks})"
            " AND (substr(checked_at,1,10) >= ?"
            "      OR checked_at = (SELECT MAX(p2.checked_at) FROM price p2"
            "                         WHERE p2.isbn = price.isbn))"
            " ORDER BY isbn, checked_at", (*isbns, window_start)):
        series.setdefault(isbn, []).append(
            (checked_at[:10], price, suspect, checked_at))

    priser = {}
    for isbn, rows in series.items():
        kort = _utvardera(rows, today.isoformat(), window_start)
        kort["isbn"] = isbn
        kort["url"] = BOKUS_BOK_URL + isbn       # §1: derived, never stored
        priser[isbn] = kort
    return {b["id"]: priser[b["isbn13"]] for b in bocker
            if b["status"] != "read" and b["isbn13"] in priser}
