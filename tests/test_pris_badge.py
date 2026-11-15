"""MC 12542 (M9a-1) — the REA badge: §4's FLOOR-EVENT identity, walked over
a synthetic price series (DESIGN-prisbevakning-v2 §4 + §8's two-leg fixture).

The door is the ONLY writer here: every price is POSTed through `pris.ingest`
with the day it belongs to as the door's own clock — the same function the
HTTP door runs, no row hand-inserted, no mock. Both the door and the read take
`now` as a parameter for §3's stated reason (a timeout, or a series, that is
not reproducible against a wall clock is not testable), so this fixture walks
weeks without touching the machine's date. The door's ±window legs are NOT
what this file tests — test_pris_door.py pins those against the real clock.

Each day is POSTed and then JUDGED before the next arrives, because that is
how a series actually exists: a day never has a future row to be read against
(§8: "assert one price, one verdict per day").

The fixture is the §8 pair:

  leg 1  100 × 8 days of history, then 100, 95, 96, 94, 100
         day 8  100 — equal to the floor ⇒ NO badge (STRICTLY-BELOW)
         day 9   95 — below the 100 floor ⇒ the event OPENS, event floor 100
         day 10  96 — STILL lit: a per-day floor would read MIN(100…, 95) = 95
                 and 96 < 95 is false, so the only reading that lights this
                 day is the open event's own 100 ⇒ PERSISTS, the SAME event
         day 11  94 — lit (still that one event)
         day 12 100 — at the event floor ⇒ CLOSES (the close IS the verdict of
                 that day); the floor re-arms from the 94 now sitting in history

  leg 2  99 × 8 days, then 99, 30, 30, 30, 105, 30, 29
         day 9   99 — equal ⇒ nothing
         day 10  30 — a >60 % drop in ONE step ⇒ G1 flags it suspect: stored,
                 FLAGGED, no badge (the ghost is not a price) and it enters no
                 floor
         day 11  30 — CONFIRMED by its second day (prev = 30, no longer a
                 drop); the floor SKIPS the suspect row and reads 99 ⇒ the
                 event OPENS at 99. This is the honest trade §4 states out
                 loud: a real >60 % drop badges on its CONFIRMATION day, one
                 day late.
         day 12  30 — lit still: a per-day floor would be 30 ⇒ not below; only
                 the event's 99 keeps it lit ⇒ PERSISTS
         day 13 105 — above the event floor ⇒ CLOSES   ← the planted-red leg
         day 14  30 — the floor re-armed to the confirmed 30 ⇒ 30 is NOT below
                 it ⇒ NO SECOND BADGE for the same low (the leg this card was
                 written for)
         day 15  29 — a kr under the re-armed floor ⇒ a NEW event, lower

PLANTED-RED (the DoD's badge-close leg): with the close made impossible in
app/priskort.py (`lit = price < event_floor` replaced by `lit = True`, so an
open event never closes), day 13 of leg 2 stayed lit — the walk answered
`..........BBB.B` where the contract says `..........BB..B`, and
`test_leg2_opens_persists_closes_and_re_arms` was the first test red. The
transcript is on MC 12542's trail.
"""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app import books, create_app, db, pris, priskort
from tests.test_browse import seed_shelf
from tests.test_pris_door import WISH_ISBN, row

# The fixture's own clock: a fixed instant, so a series spanning weeks is the
# same series tomorrow. Nothing about a badge may depend on the date a test
# happens to run on.
NU = datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def hyllan(tmp_path, monkeypatch):
    """The configured shelf with one wish carrying an isbn, plus its open
    connection: the door and the read run over the same connection the app
    hands a view (`db.get_db`, foreign keys on)."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    with sqlite3.connect(tmp_path / "liselott.db") as c:
        c.execute("UPDATE book SET isbn13 = ? WHERE id = 5", (WISH_ISBN,))
    app = create_app()
    app.testing = True
    with app.app_context():
        yield db.get_db()


def dar_for_dag(conn, fran, *prices):
    """The series, ONE DAY APART, each day POSTed with its own clock and
    judged before the next one arrives — the daily runner replayed. Returns
    that day's card row (the same dict /bibliotek renders) per day. Day index
    `fran` counts from NU; the day a row belongs to is the day it is judged on
    unless a test says otherwise."""
    dagar = []
    for i, price in enumerate(prices):
        dag = NU + timedelta(days=fran + i)
        pris.ingest(conn, [row(price=price, when=dag)], now=dag)
        dagar.append(priskort.card_prices(conn, books.load_books(conn),
                                          now=dag).get(5))
    return dagar


# ── leg 1: one event, and the bounce that proves it is ONE ──────────────────
def test_leg1_opens_once_persists_through_the_bounce_then_closes(hyllan):
    """§8 leg 1 — 8 days of 100, then 100, 95, 96, 94, 100."""
    dagar = dar_for_dag(hyllan, 0, *[100] * 8, 100, 95, 96, 94, 100)
    assert "".join("B" if d["rea"] else "." for d in dagar) == ".........BBB."
    assert dagar[8]["rea"] is False            # equal to the floor is NOT below
    assert dagar[10]["rea"] is True            # 96: only the EVENT floor (100)
    #                                           lights this day, not its own 95
    assert dagar[12]["rea"] is False           # the close, AT the event floor


def test_leg1_the_price_is_there_on_every_day_of_the_walk(hyllan):
    """§1: the CURRENT row is MAX(checked_at) and it is on the card every day
    of the walk, badge or not — a price is a fact, a badge is a verdict about
    it. None of these days is stale: each row is judged on its own day."""
    dagar = dar_for_dag(hyllan, 0, *[100] * 8, 100, 95, 96, 94, 100)
    assert [d["price"] for d in dagar[8:]] == [100, 95, 96, 94, 100]
    assert [d["stale"] for d in dagar] == [False] * 13


# ── leg 2: the G1 day, the confirmation, the close, the re-arm ──────────────
def test_leg2_opens_persists_closes_and_re_arms(hyllan):
    """§8 leg 2 — the four behaviours in one walk. The close (day 13) and the
    missing second badge (day 14) are the two this card exists to pin."""
    dagar = dar_for_dag(hyllan, 0, *[99] * 8, 99, 30, 30, 30, 105, 30, 29)
    assert "".join("B" if d["rea"] else "." for d in dagar) == "..........BB..B"
    assert dagar[9]["price"] == 30 and dagar[9]["rea"] is False   # stored, flagged
    assert dagar[12]["stale"] is False                            # close is TODAY
    assert dagar[13]["price"] == 30                              # the same low…
    assert dagar[13]["rea"] is False                             # …no second badge
    assert dagar[14]["rea"] is True                              # a NEW lower event


def test_the_first_big_drop_is_flagged_by_the_door_not_by_this_file(hyllan):
    """The suspect flag this engine reads is G1's, computed on the way IN: the
    30 arriving after a 99 is stored (the price is real data) and flagged (the
    drop is impossible to believe unseen)."""
    dagar = dar_for_dag(hyllan, 0, *[99] * 8, 30)
    assert dagar[-1]["price"] == 30 and dagar[-1]["rea"] is False
    flag = hyllan.execute("SELECT suspect FROM price WHERE price = 30").fetchone()
    assert flag == (1,)


def test_a_ghost_price_never_enters_the_floor(hyllan):
    """§4's false-PREVENITION leg, built so it CANNOT be satisfied by a build
    that lets the ghost in: 8 days of 99, a ghost 9 (G1 flags it on arrival),
    a 200 that closes anything the ghost opened, then 90.

    * the ghost's own day is dark (rule 4: its row is suspect);
    * 200 is dark (it is not below anything);
    * 90 LIGHTS: the floor skips the ghost and reads 99, so 90 is a new low
      inside 90 days. A build that let the suspect 9 into the floor finds the
      floor to be 9, answers "90 is not below 9" and stays silent through a
      real REA — which is the bug §4 names, and this is the leg that sees it
      (a simpler 95-after-the-ghost series does NOT: the ghost's own event
      would have kept that one lit, which is exactly why the 200 is in here)."""
    dagar = dar_for_dag(hyllan, 0, *[99] * 8, 9, 200, 90)
    assert dagar[-3]["rea"] is False        # the ghost's own day
    assert dagar[-2]["rea"] is False        # 200: above everything
    assert dagar[-1]["rea"] is True         # 90 under a floor of 99


def test_equal_to_the_floor_is_never_below_it(hyllan):
    """STRICTLY-BELOW, both sides in one walk: twelve days of 100 never badge;
    one kr under the floor opens."""
    dagar = dar_for_dag(hyllan, 0, *[100] * 13)
    assert "B" not in "".join("B" if d["rea"] else "." for d in dagar)
    assert dar_for_dag(hyllan, 13, 99)[-1]["rea"] is True


@pytest.mark.parametrize("historik, forvantad", [(7, False), (8, True)])
def test_depth_is_eight_observations_inside_the_window(hyllan, historik,
                                                      forvantad):
    """§4 rule 2, measured at the boundary: with SEVEN distinct earlier days a
    price at 41 % of the floor is not enough history to call anything a
    bottom; with EIGHT it is. Same price, same floor — only depth moved."""
    dagar = dar_for_dag(hyllan, 0, *[100] * historik, 41)
    assert dagar[-1]["rea"] is forvantad


def test_rows_older_than_the_window_are_not_the_floor(hyllan):
    """PRICE_WINDOW_DAYS = 90 is what makes the printed claim ("lower than any
    accepted price in 90 days") true: a 30 from a hundred days back is still
    in the table — and is still NOT today's floor, so 95 reads as a new low
    inside the window."""
    dar_for_dag(hyllan, 0, 30)
    dagar = dar_for_dag(hyllan, 100, *[99] * 8, 95)
    assert dagar[-1]["rea"] is True
    assert dagar[-1]["price"] == 95
    gammal = hyllan.execute("SELECT count(*) FROM price"
                            " WHERE price = 30").fetchone()[0]
    assert gammal == 1                       # pruned by NOTHING before its time


def test_a_stale_price_shows_as_stale_and_can_never_badge(hyllan):
    """§5's outage posture, the badge half: the series stops, the price stays,
    the day it was seen stays on the card — and no badge is lit on a day the
    price was never observed. Day 11's 94 IS still under the event floor."""
    dagar = dar_for_dag(hyllan, 0, *[100] * 8, 100, 95, 96, 94)
    assert dagar[-1]["rea"] is True
    still = priskort.card_prices(hyllan, books.load_books(db.get_db()),
                                 now=NU + timedelta(days=20))[5]
    assert still["stale"] is True and still["rea"] is False
    assert still["price"] == 94
    assert still["checked_date"] == "2026-03-13"          # 11 days after NU


def test_the_card_row_carries_the_series_facts_not_this_files_opinion(hyllan):
    """The read model's own contract (§1): the price, the moment it belongs to,
    the day derived from it, the stale flag and the isbn it came from — ONE
    dict per wish, computed once, with the deep link derived server-side."""
    dagar = dar_for_dag(hyllan, 0, *[100] * 8, 95)
    kortet = dagar[-1]
    assert kortet["price"] == 95
    assert kortet["checked_at"] == "2026-03-10T12:00:00Z"
    assert kortet["checked_date"] == "2026-03-10"
    assert kortet["isbn"] == WISH_ISBN
    assert kortet["url"] == "https://www.bokus.com/bok/" + WISH_ISBN
    assert kortet["stale"] is False


def test_a_wish_without_a_single_observation_gets_no_row_at_all(hyllan):
    """§5: "No observation ⇒ no markup". The map simply does not carry the
    card — there is nothing for a template to render a dash from."""
    assert priskort.card_prices(hyllan, books.load_books(db.get_db()),
                                now=NU) == {}


def test_a_read_books_price_never_reaches_a_card(hyllan):
    """§5's scope, on the read side: the door refuses a read book's isbn, and
    even a price row that got in by some other door stays off the page — the
    map is built from the WISHLIST cards it was handed, and only those."""
    dar_for_dag(hyllan, 0, *[100] * 8, 95)
    hyllan.execute("INSERT INTO price (isbn, book_id, retailer, price,"
                       " checked_at) VALUES ('9789173710015', 2, 'bokus', 950,"
                       " '2026-03-10T12:00:00Z')")
    alla = books.load_books(hyllan)
    priser = priskort.card_prices(hyllan, alla, now=NU + timedelta(days=8))
    assert 2 not in priser                      # the read row's price stays off
    assert list(priser) == [5]                  # the wish's own price is on
