"""M9a-1 — POST /pris: the price door (DESIGN-prisbevakning-v2 §6e + §4 rule 4).

One door, one table (app/schema.sql's `price`): the daily runner POSTs a JSON
array of {isbn, retailer, price, currency, checked_at} and NOTHING else about
a row is client-owned — `book_id` is resolved HERE, `ok` is constant, `suspect`
is computed HERE (G1, §4 rule 4 — the DOOR is the named evaluator), the deep
link is derived from `isbn` at display time (§5), and the dedup is the
`ux_price_isbn_day` UPSERT (no SELECT-then-INSERT race beside it).

The §6e per-row contract, in the order the counters are named:

* `rejected_shape` — not an object, `isbn` not exactly 13 ASCII digits,
  `retailer` ≠ "bokus", `currency` ≠ "SEK", `price` not an integer 1..20000,
  `checked_at` not the ISO-UTC shape §1 pins (auth.utcnow_iso's own format:
  full match, no offset form, no fractional seconds, no trailing date-only).
  Pre-validated so the table's CHECK constraints can never answer 500.
* `rejected_date` — a real timestamp outside the CLAMPED window
  [now − 2 d, now + 5 min] (§4 rule 5, the backdate defence: history can only
  arrive stamped today or the last two days, so a stored `price=1` row cannot
  poison the 90-day floor from six months back. The named residual rides with
  it: a holder of the credential can still backdate by ≤ 2 days).
* `rejected_unknown` — the isbn resolves to no WISHLIST row. M9a's whole fetch
  scope is the wishlist (`WHERE isbn13 = ? AND status = 'wishlist'`), so a
  price for a read book has nowhere to be displayed and nowhere to be checked.
  Multiple wishes sharing an isbn resolve MIN(id) — they share ONE series
  anyway (§1: the price is the book's). §6e's response shape names no key for
  the ambiguity, so it is resolved, never counted beside the pinned shape.

One failure class per row, first refusal wins. G1 runs BEFORE the upsert and
compares against the latest observation strictly BEFORE the written row's day
(the F-b cure: it keeps today's own re-ask from suppressing today's badge, and
makes the verdict arrival-order-independent), flagging a >60 % drop as suspect.

Posture (§6e): /pris joins auth.TOKENLESS_POSTS — no CSRF token, foreign
Origin 400s, login throttle and Secure cookie unchanged — and the guard runs
BEFORE the token rule, so an anonymous POST meets the uniform 302. The
exemption is TOKENLESS, not guardless, and /pris is NOT in the §6.4 read
allow-list: writing prices is not something a stranger may do.
"""
from datetime import datetime, timedelta, timezone

from flask import jsonify, request

from app import auth, db

PRIS_RETAILER = "bokus"           # M9a fetches Bokus only (§6c)
PRIS_CURRENCY = "SEK"             # §6c/RECIPE-DECISION: one currency per row
PRICE_MIN, PRICE_MAX = 1, 20_000  # §6e (the same bounds the table CHECKs)
MAX_PRIS_BODY = 65_536            # §6e: ≈120 B/row × ≤500 rows + bracket slack
MAX_PRIS_ROWS = 500               # §6e: ≈200 wishes + duplicate isbns + a day's retry
RETENTION_DAYS = 730              # §1: ONE prune per accepted POST (backup.KEEP posture)
CHECKED_BACK_S = 2 * 86400        # §4 rule 5: the clamp window, back…
CHECKED_FWD_S = 5 * 60            # …and forward (a runner's clock skew, bounded)
G1_DROP_NUM, G1_DROP_DEN = 2, 5   # §4 rule 4: price < 2/5 × prev ⇒ suspect

STAMP_FMT = "%Y-%m-%dT%H:%M:%SZ"  # auth.utcnow_iso's own shape (§1)
LENGTH_REQUIRED = (
    "Innehållets längd (Content-Length) saknas — dörren vägrar gissa sig "
    "till vad transporten skickade: skicka listan igen med längden i höljet."
    " Ingen prisrad är lagrad")   # the /seed //bundle F-E2 posture, same rule
ROWS_TOO_BIG = ("Prislistan är {antal} rader — budgetet är {max} rader per "
                "anrop (§6e); dela upp den. Ingen prisrad är lagrad")
NOT_A_LIST = ("Prislistan är inte en JSON-array av objekt — dörren tar "
              "emot [{isbn, retailer, price, currency, checked_at}, …]. "
              "Ingen prisrad är lagrad")


def _obs(row, now):
    """The §6e per-row SHAPE + DATE pass: (reject-class, None) or (None, obs).
    Integer G1 and the table CHECKs both lean on this being exact — a float
    that merely LOOKS integral (`99.0`) is rejected, never coerced."""
    if not isinstance(row, dict):
        return "shape", None
    isbn, price = row.get("isbn"), row.get("price")
    if not (isinstance(isbn, str) and len(isbn) == 13 and isbn.isdigit()):
        return "shape", None            # 13 ASCII digits, no hyphens, no ints
    if isinstance(price, bool) or not isinstance(price, int):
        return "shape", None
    if not PRICE_MIN <= price <= PRICE_MAX:
        return "shape", None
    if row.get("retailer") != PRIS_RETAILER or row.get("currency") != PRIS_CURRENCY:
        return "shape", None
    stamp = row.get("checked_at")
    if not (isinstance(stamp, str) and len(stamp) == 20
            and stamp.endswith("Z")):
        return "shape", None
    try:
        when = datetime.strptime(stamp, STAMP_FMT).replace(tzinfo=timezone.utc)
    except ValueError:
        return "shape", None            # 2026-02-31T… is a shape, not a date
    if when < now - timedelta(seconds=CHECKED_BACK_S):
        return "date", None
    if when > now + timedelta(seconds=CHECKED_FWD_S):
        return "date", None
    return None, {"isbn": isbn, "price": price, "checked_at": stamp,
                  "day": stamp[:10]}


def _wish_id(conn, isbn):
    """The wishlist-only resolve (§6e): no wish, no row. MIN(id) when several
    wishes carry the isbn — one series, one metadata id (the series is keyed
    by isbn, so the choice never moves a price away from its book)."""
    row = conn.execute("SELECT MIN(id) FROM book WHERE isbn13 = ?"
                       " AND status = 'wishlist'", (isbn,)).fetchone()
    return row[0]


def _prev(conn, isbn, day, med):
    """G1's comparison point: the latest observation of this isbn STRICTLY
    before the written row's day — from the table as the POST found it AND
    from the days this same POST carries (`med`), whichever is later. Both
    halves matter: the table alone would let a payload that restates yesterday
    plus a new today judge today against a stale yesterday, and a per-row
    re-read after each write would make the verdict depend on the order the
    rows arrived. As written, `prev` is a function of the PAYLOAD plus the
    table BEFORE this POST wrote anything — order-independent by
    construction, which is what §4 asks of a door that may be re-run."""
    rad = conn.execute("SELECT checked_at, price FROM price WHERE isbn = ?"
                       " AND substr(checked_at,1,10) < ?"
                       " ORDER BY checked_at DESC LIMIT 1", (isbn, day)).fetchone()
    tidigare = [(o["checked_at"], o["price"]) for o in med if o["day"] < day]
    if rad is not None:
        tidigare.append(tuple(rad))
    return max(tidigare, default=None)


def _suspect(prev, price):
    """G1 (§4 rule 4), the named evaluator: no prev ⇒ no suppression (the
    FIRST observation is never suspect — the ghost it would have been read off
    does not exist). Integer arithmetic (2·prev vs 5·price), because a float
    0.4 would decide the 60 % boundary differently at the edge."""
    if prev is None:
        return 0
    return 1 if price * G1_DROP_DEN < prev[1] * G1_DROP_NUM else 0


def _store(conn, obs, book_id, suspect):
    """THE dedup (§6e): ON CONFLICT DO UPDATE against ux_price_isbn_day, the
    auth.set_setting idiom. Returns "inserted" or "updated" — the day key is
    asked for BEFORE the write, because that is the only honest way to tell a
    first observation from today's re-ask."""
    known = conn.execute("SELECT 1 FROM price WHERE isbn = ? AND retailer = ?"
                         " AND substr(checked_at,1,10) = ? LIMIT 1",
                         (obs["isbn"], PRIS_RETAILER, obs["day"])).fetchone()
    conn.execute(
        "INSERT INTO price (isbn, book_id, retailer, price, currency,"
        " checked_at, suspect) VALUES (?,?,?,?,?,?,?)"
        " ON CONFLICT (isbn, retailer, substr(checked_at,1,10)) DO UPDATE SET"
        " book_id = excluded.book_id, price = excluded.price,"
        " checked_at = excluded.checked_at, suspect = excluded.suspect",
        (obs["isbn"], book_id, PRIS_RETAILER, obs["price"], PRIS_CURRENCY,
         obs["checked_at"], suspect))
    return "updated" if known else "inserted"


def ingest(conn, rows, now=None):
    """One POST's rows through the whole per-row contract; returns the §6e
    aggregate counters (zero book data — the response is the only output).
    `now` is a parameter, not a clock read, for exactly the reason §3
    parameterises its timeouts: the day-by-day series a badge test has to
    build cannot be built against a wall clock it does not own. Production
    passes nothing and gets utcnow.

    G1 runs for EVERY row before ANY row is written, and its `prev` sees the
    table as this POST found it plus the earlier days this POST itself
    carries, so a payload with two days of one isbn (a restated day plus a new
    one) answers the same verdicts in either order — the same arrival-order
    independence §4 pins for the same-day double-upsert."""
    now = now or datetime.now(timezone.utc)
    counts = {k: 0 for k in ("accepted", "inserted", "updated", "suspect",
                             "rejected_unknown", "rejected_shape",
                             "rejected_date")}
    validated = []
    for row in rows:
        reject, obs = _obs(row, now)
        if reject:
            counts[f"rejected_{reject}"] += 1
            continue
        book_id = _wish_id(conn, obs["isbn"])
        if book_id is None:
            counts["rejected_unknown"] += 1
            continue
        obs["book_id"] = book_id
        validated.append(obs)
    for obs in validated:
        med = [o for o in validated
               if o["isbn"] == obs["isbn"] and o is not obs]
        obs["suspect"] = _suspect(_prev(conn, obs["isbn"], obs["day"], med),
                                 obs["price"])
    for obs in validated:
        counts[_store(conn, obs, obs["book_id"], obs["suspect"])] += 1
        counts["accepted"] += 1
        counts["suspect"] += obs["suspect"]
    if counts["accepted"]:
        conn.execute("DELETE FROM price WHERE checked_at < ?",
                     ((now - timedelta(days=RETENTION_DAYS)).strftime(STAMP_FMT),))
    conn.commit()
    return counts


def init_pris(app):

    @app.post("/pris")
    def pris_door():
        """The machine door (§6e). No Content-Length, no read (F-E2); body
        over MAX_PRIS_BODY bytes 413s naming the budget; more than
        MAX_PRIS_ROWS rows 400s naming it — both BEFORE a row is parsed, so
        neither ever touches the DB. The payload must be a JSON array; a
        single object is a shape error of the PAYLOAD, not a row, and 400s."""
        if request.headers.get("Content-Length") is None:
            return LENGTH_REQUIRED, 411
        raw = request.get_data()
        if len(raw) > MAX_PRIS_BODY:
            return (f"Prislistan är {len(raw)} byte — budgetet är "
                    f"{MAX_PRIS_BODY} byte per anrop (§6e); dela upp den. "
                    "Ingen prisrad är lagrad"), 413
        rows = request.get_json(force=True, silent=True)
        if not isinstance(rows, list):
            return NOT_A_LIST, 400
        if len(rows) > MAX_PRIS_ROWS:
            return ROWS_TOO_BIG.format(antal=len(rows),
                                        max=MAX_PRIS_ROWS), 400
        return jsonify(ingest(db.get_db(), rows))
