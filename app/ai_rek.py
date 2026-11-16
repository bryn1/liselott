"""M11 (MC 12597, design MC 12590) — the "AI rekommenderar" category.

One module, one concern: the recommendation SURFACE. It owns the machine
ingest door POST /ai-rek (the fifth door, the /pris credential posture
verbatim — MC 12546's dedicated door token, checked IN THE DOOR before any
body parse, fail-closed 503 when the env is unset, one uniform 401 copy for
absent-or-wrong), the owner's accept/decline POSTs (session + CSRF like
every browser POST — NOT a TOKENLESS route), the page view GET
/rekommendationer and the classic list's dismiss POST /djem — both MOVED
out of routes.py unchanged (endpoint names, URLs and behaviour stand;
routes.py ends at <=400 lines, MC 12597's hygiene move).

The lifecycle rules MC 12590 §d pins, all door-side so the UI cannot be
blamed: the upsert matches on `rec_key` (isbn13 when present, else
seed.book_key — THE repo key mechanism); a row whose state is 'accept' or
'decline' is NEVER overwritten and never resurrected (counters
kept_accept/kept_decline); `ts` is the SERVER clock, no client stamp, no
backdate surface. Accept is not a second wishlist mechanism: it flips the
row and writes the wish through onska.skapa_onska — one wish writer, two
callers. Decline is the state flip + `declined_at`; no un-decline door in
M11 (the task pins: declines never resurface).
"""
import hmac
import math
import os
import re

from flask import abort, jsonify, render_template, request, session

from app import auth, db, onska, recommend, seed

MAX_AI_REK_BODY = 262_144           # ≈400 B/row × 500 rows + bracket slack
MAX_AI_REK_ROWS = 500               # one generation pool + retry margin
AI_REK_TOKEN_ENV = "AI_REC_DOOR_TOKEN"   # the dedicated door credential
AI_REK_HEADER = "X-Ai-Rek-Token"    # ... and the header it arrives on
# MC 12597 arms the door ONLY on a well-formed env: exactly 64 lowercase
# hex chars (secrets.token_hex(32)'s shape). The ENV is validated, never the
# request's header — the header compare stays byte-exact, so the shape rule
# cannot become an oracle. A malformed armed env is the DISARMED door (503),
# never a weaker one.
TOKEN_SHAPE = re.compile(r"[0-9a-f]{64}")

TOKEN_UNARMED = ("AI-rek-dörren är inte aktiverad på den här servern — "
                 "ingen rekommendation är lagrad")            # 503, fail-closed
TOKEN_REFUSED = ("Dörrnyckeln saknas eller är fel — ingen rekommendation är "
                 "lagrad")           # 401, ONE uniform copy (no oracle)
LENGTH_REQUIRED = (
    "Innehållets längd (Content-Length) saknas — dörren vägrar gissa sig "
    "till vad transporten skickade: skicka listan igen med längden i höljet."
    " Ingen rekommendation är lagrad")   # the /pris F-E2 posture, same rule
ROWS_TOO_BIG = ("AI-listan är {antal} rader — budgetet är {max} rader per "
                "anrop; dela upp den. Ingen rekommendation är lagrad")
NOT_A_LIST = ("AI-listan är inte en JSON-array av objekt — dörren tar emot "
              "[{title, author_name, isbn13, year, reason, source, fit}, …]. "
              "Ingen rekommendation är lagrad")

DISMISS_KINDS = {"book": "book", "cand": "candidate"}   # moved with /djem


def _door_refused():
    """The door's OWN first word, the /pris `_door_refused` verbatim
    (MC 12546 semantics, MC 12597's 64-hex arming on top): env read PER
    REQUEST (the app's own env idiom — rotation = set the env, restart);
    unset, empty or malformed ⇒ 503 for EVERY POST, the owner's session
    included (fail-closed is the shipped default). A valid owner session
    rides the door WITHOUT the token; every other caller must present
    `X-Ai-Rek-Token` byte-equal under hmac.compare_digest (constant-time),
    absent and wrong answering THE SAME copy — no oracle to walk."""
    expected = os.environ.get(AI_REK_TOKEN_ENV) or ""
    if not TOKEN_SHAPE.fullmatch(expected):
        return TOKEN_UNARMED, 503
    if session.get(auth.SESSION_FLAG):
        return None        # her own tools ride the session she already holds
    sent = request.headers.get(AI_REK_HEADER, "")
    if hmac.compare_digest(sent.encode("utf-8"), expected.encode("utf-8")):
        return None
    return TOKEN_REFUSED, 401


def _text(value):
    """A non-empty string stripped, or None — the shape vocabulary the /pris
    `_obs` idiom uses for its text fields."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _obs(row):
    """The per-row SHAPE pass, the /pris `_obs` idiom: (reject-class, None)
    or (None, obs). title/reason/source non-empty; author_name NULL or
    non-empty (the column is nullable); isbn13 NULL or exactly 13 ASCII
    digits (the redigera isascii-and-isdigit idiom); year NULL or int
    1000..2100; fit a finite int/float in [0,1] (the fit score's own
    domain — NOT a bool, NaN/Infinity rejected so ORDER BY fit cannot read
    garbage). Pre-validated so the table's CHECKs can never answer 500.
    `rec_key` and `ts` are computed HERE — nothing about identity or time
    is client-owned."""
    if not isinstance(row, dict):
        return "shape", None
    title = _text(row.get("title"))
    reason = _text(row.get("reason"))
    source = _text(row.get("source"))
    if title is None or reason is None or source is None:
        return "shape", None
    author = row.get("author_name")
    if author is not None and _text(author) is None:
        return "shape", None
    author = _text(author)
    isbn = row.get("isbn13")
    if isbn is not None and not (isinstance(isbn, str) and len(isbn) == 13
                                 and isbn.isascii() and isbn.isdigit()):
        return "shape", None
    year = row.get("year")
    if year is not None and (isinstance(year, bool)
                             or not isinstance(year, int)
                             or not 1000 <= year <= 2100):
        return "shape", None
    fit = row.get("fit")
    if (isinstance(fit, bool) or not isinstance(fit, (int, float))
            or not math.isfinite(fit) or not 0.0 <= fit <= 1.0):
        return "shape", None
    return None, {"rec_key": isbn if isbn is not None
                  else seed.book_key(title, [author or ""]),
                  "isbn13": isbn, "title": title, "author_name": author,
                  "year": year, "reason": reason, "source": source,
                  "fit": float(fit)}


def ingest(conn, rows):
    """One POST's rows through shape + upsert; returns the aggregate
    counters and ZERO book data (the echo rule, pris.py's response). The
    upsert asks for the key BEFORE the write (the pris `_store` posture —
    the only honest way to tell a first sighting from a refresh):
    state 'new' refreshes in place, no key INSERTs, and a row in state
    'accept' or 'decline' is counted kept and left UNTOUCHED — the one
    rule that makes "declines never resurface" the door's promise, not
    the page's."""
    counts = {k: 0 for k in ("accepted", "inserted", "updated",
                             "kept_accept", "kept_decline",
                             "rejected_shape")}
    nu = auth.utcnow_iso()               # SERVER clock only, one read/POST
    for row in rows:
        reject, obs = _obs(row)
        if reject:
            counts["rejected_shape"] += 1
            continue
        rad = conn.execute("SELECT id, state FROM ai_rek WHERE rec_key = ?",
                           (obs["rec_key"],)).fetchone()
        if rad is not None and rad[1] in ("accept", "decline"):
            counts[f"kept_{rad[1]}"] += 1
            continue
        if rad is not None:              # state 'new' ⇒ refresh in place
            conn.execute(
                "UPDATE ai_rek SET title = ?, author_name = ?, isbn13 = ?,"
                " year = ?, reason = ?, source = ?, fit = ?, ts = ?"
                " WHERE id = ?",
                (obs["title"], obs["author_name"], obs["isbn13"], obs["year"],
                 obs["reason"], obs["source"], obs["fit"], nu, rad[0]))
            counts["updated"] += 1
        else:
            conn.execute(
                "INSERT INTO ai_rek (rec_key, isbn13, title, author_name,"
                " year, reason, source, fit, ts) VALUES (?,?,?,?,?,?,?,?,?)",
                (obs["rec_key"], obs["isbn13"], obs["title"],
                 obs["author_name"], obs["year"], obs["reason"],
                 obs["source"], obs["fit"], nu))
            counts["inserted"] += 1
        counts["accepted"] += 1
    conn.commit()
    return counts


def for_page(conn):
    """The owner page's live reads, best fit FIRST (`fit DESC`, MC 12597's
    ordering; ties break on id for a stable render). state='new' only —
    accepted and declined rows never come back to the page."""
    kolumner = ("id", "title", "author_name", "year", "reason", "source",
                "fit")
    rader = conn.execute(
        f"SELECT {', '.join(kolumner)} FROM ai_rek WHERE state = 'new'"
        " ORDER BY fit DESC, id").fetchall()
    return [dict(zip(kolumner, rad)) for rad in rader]


def init_ai_rek(app):

    @app.post("/ai-rek")
    def ai_rek_door():
        """The machine door — the /pris envelope verbatim: credential
        FIRST, then no Content-Length no read (411), then the byte budget
        (413) and the row budget (400), each naming its own number BEFORE
        a single row is parsed, so none of them ever touches the DB. A
        payload that is not a JSON array is a payload-shape 400. Foreign
        Origin already 400s at the GUARD (auth.TOKENLESS_POSTS: origin-
        checked, token-exempt); GET and every other method on /ai-rek keep
        the guard's uniform 302 (auth._is_ai_rek_door is POST-only)."""
        refused = _door_refused()
        if refused is not None:
            return refused
        if request.headers.get("Content-Length") is None:
            return LENGTH_REQUIRED, 411
        raw = request.get_data()
        if len(raw) > MAX_AI_REK_BODY:
            return (f"AI-listan är {len(raw)} byte — budgetet är "
                    f"{MAX_AI_REK_BODY} byte per anrop; dela upp den. "
                    "Ingen rekommendation är lagrad"), 413
        rows = request.get_json(force=True, silent=True)
        if not isinstance(rows, list):
            return NOT_A_LIST, 400
        if len(rows) > MAX_AI_REK_ROWS:
            return ROWS_TOO_BIG.format(antal=len(rows),
                                        max=MAX_AI_REK_ROWS), 400
        return jsonify(ingest(db.get_db(), rows))

    @app.post("/ai-rek/<int:rek_id>/accept")
    def ai_rek_accept(rek_id):
        """Owner POST: guard + CSRF already ran (session-guarded, token
        required — the /djem pattern, NOT a TOKENLESS machine route).
        Unknown id ⇒ plain 404, echo nothing (the /djem idiom). The flip
        is COMMITTED FIRST (MC 12597's order) — skapa_onska owns its own
        commit/rollback, so flipping after its commit would leave a wish
        with no state, and flipping inside its transaction would let its
        UNIQUE rollback undo the flip; a committed flip first cannot undo,
        and "redan" (already wished) still counts as the accept succeeding.
        A row already decided ('accept' or 'decline') is a no-op redirect:
        the second accept writes no second wish, the declined stay down."""
        conn = db.get_db()
        rad = conn.execute("SELECT title, author_name, isbn13, year, state"
                           " FROM ai_rek WHERE id = ?", (rek_id,)).fetchone()
        if rad is None:
            abort(404)                       # the 404 page echoes nothing
        if rad[4] != "new":
            return auth.redirect_prefixed("/rekommendationer")
        conn.execute("UPDATE ai_rek SET state = 'accept', ts = ?"
                     " WHERE id = ?", (auth.utcnow_iso(), rek_id))
        conn.commit()
        onska.skapa_onska(conn, rad[0], rad[1] or "",
                          isbn13=rad[2], year=rad[3])   # THE wish writer
        return auth.redirect_prefixed("/rekommendationer")

    @app.post("/ai-rek/<int:rek_id>/decline")
    def ai_rek_decline(rek_id):
        """Owner POST, same posture as accept: decline is the ONE flip —
        state + declined_at, both server-stamped. Already-decided rows are
        a no-op redirect (never an error, never an un-decline)."""
        conn = db.get_db()
        rad = conn.execute("SELECT state FROM ai_rek WHERE id = ?",
                           (rek_id,)).fetchone()
        if rad is None:
            abort(404)                       # the 404 page echoes nothing
        if rad[0] == "new":
            nu = auth.utcnow_iso()
            conn.execute("UPDATE ai_rek SET state = 'decline', ts = ?,"
                         " declined_at = ? WHERE id = ?", (nu, nu, rek_id))
            conn.commit()
        return auth.redirect_prefixed("/rekommendationer")

    @app.get("/rekommendationer")
    def rekommendationer():
        """T6.2 — the §8 page, MOVED here by MC 12597 (the <=400-line move
        out of routes.py; same URL, same endpoint name — routes.py's slash
        rule still points at this view). The engine's top 12, best first,
        plus the M11 AI section on top (for_page, fit DESC). rated==0 is
        NOT an error state: the plan's empty-state copy answers and the
        wishlist-led list still renders (the t=0 leg)."""
        conn = db.get_db()
        rated = conn.execute("SELECT COUNT(*) FROM book"
                             " WHERE rating IS NOT NULL").fetchone()[0]
        return render_template("rekommendationer.html",
                               recs=recommend.top_recommendations(conn, 12),
                               ai_recs=for_page(conn),
                               rated=rated, current="rekommendationer")

    @app.post("/djem/<kind>/<int:item_id>")
    def djem(kind, item_id):
        """T6.2 — "Visa inte igen", MOVED with the page: the §8 dismissed
        row, keyed 'book:<id>' for a wish and 'cand:<id>' for a pool card
        (P2-3). The engine excludes the key from the top-12; PRIMARY KEY
        makes a repeated click a no-op, never an error. The table name
        comes from a fixed whitelist dict, never from the URL."""
        if kind not in DISMISS_KINDS:
            abort(404)
        conn = db.get_db()
        if conn.execute(f"SELECT 1 FROM {DISMISS_KINDS[kind]} WHERE id = ?",
                        (item_id,)).fetchone() is None:
            abort(404)                       # the 404 page echoes nothing
        conn.execute("INSERT OR IGNORE INTO dismissed (key, ts) VALUES (?,?)",
                     (f"{kind}:{item_id}", auth.utcnow_iso()))
        conn.commit()
        return auth.redirect_prefixed("/rekommendationer")

    # F-3's slash rule MOVED with the view (MC 12597): registered DIRECTLY
    # under the canonical one so url_for keeps building the canonical
    # (shorter) URL — the first rule of an endpoint is the one it builds.
    app.add_url_rule("/rekommendationer/", endpoint="rekommendationer")
