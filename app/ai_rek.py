# 531 lines > 400 (MC 12616; MC 12643's read door rides THIS module, the
# door's ONE credential family — not a sibling): the door's ONE ingest
# chain — shape pass, identity matcher, full-swap sweep, the settle and
# its commit — is one atomic "new generation" transaction, and cutting the
# sweep into a sibling file would scatter that guarantee
# (coding-discipline header REASON; the split stays scheduled, a REASON
# never absolves it).
"""M11 (MC 12597, design MC 12590) — the "AI rekommenderar" category.

One module, one concern: the recommendation SURFACE. It owns the machine
ingest door POST /ai-rek (the ONLY door-token route standing since MC 12606
retired the price door /pris, whose credential posture this file copied
verbatim — MC 12546's dedicated door token, checked IN THE DOOR before any
body parse, fail-closed 503 when the env is unset, one uniform 401 copy for
absent-or-wrong. Every `/pris`/`pris.py` citation further down names THAT
retired door as the design precedent, never a live route), the owner's
accept/decline POSTs (session + CSRF like every browser POST — NOT a
TOKENLESS route), the page view GET
/rekommendationer and the classic list's dismiss POST /djem — both MOVED
out of routes.py unchanged (endpoint names, URLs and behaviour stand;
routes.py ends at <=400 lines, MC 12597's hygiene move).

The lifecycle rules MC 12590 §d pins, all door-side so the UI cannot be
blamed — with the MC 12602 DA-gate fixes: the upsert matches on the WHOLE
book identity, not one ingest key (`_bok_rad`: the UNIQUE `rec_key`, the
isbn, and the §5.3 normalized title+author key through `onska.wish_key` —
ONE identity mechanism, so a decline holds however the book is spelled and
a re-spelling cannot mint a second card, F-P1-1); a row in state 'accept'
or 'decline' is NEVER overwritten and never resurrected (counters
kept_accept/kept_decline); the INSERT rides `ON CONFLICT(rec_key) DO
NOTHING` + re-ask, never an IntegrityError under concurrent POSTs
(F-P3-7); `ts` is the SERVER clock, no client stamp, no backdate surface;
fit is baked CHECKed [0,1] and `kategori` (nyhet/klassiker/blandad) rides
the ingest (F-P4-1). Accept is not a second wishlist mechanism: the wish
goes through onska.skapa_onska — one wish writer, two callers, THE §7 isbn
validation inside it (F-P2-2) — and the state flip lands only after the
wish succeeded (F-P2-3). Decline is the state flip + `declined_at`; no
un-decline door in M11 (the task pins: declines never resurface).

MC 12616 (M11-N8a, PLAN §d completion) adds the door's OPTIONAL full-swap
envelope `{"generation": [ …rows… ]}`: the POSTed list is the COMPLETE new
generation and `_sweepa` deletes the state='new' rows whose identity is
ABSENT from it — identity is THE SAME union `_bok_rad` matches on, asked
inverted through `_samma_bock` (ONE mechanism, no second "same book" rule);
accept/decline rows are NEVER deleted (the DELETE rides the same
state='new' guard as the duppar merge), a full-swap of ZERO rows is
REFUSED fail-loud (`EMPTY_GENERATION`, rows kept) and the answer gains
`deleted_n`. A payload WITHOUT the "generation" key is today's upsert,
byte-identical, posture unchanged (fail-closed 503, 64-hex 401, generic
disarmed copy, uniform 302).

MC 12643 (M11-N9a, the owner's ruling "A" — chat 2026-11-17, accepting:
the generator gets the COMPLETE read-title list via the existing machine
door; public scope unchanged, graded + wishlist only; read books are
never re-recommended) adds the door's READ twin: GET /ai-rek/library-keys
answers EVERY `bok` row as {titel, forfattare, status} — read AND
wishlist — through THE SAME `_door_refused` credential checked FIRST.
This route joins NO public allow-list (public scope UNCHANGED): the
guard lets the GET through only with the door header riding
(auth._is_ai_rek_keys), so an anonymous reader without it gets the
guard's uniform 302, the identical answer GET /ai-rek gives.
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

TOKEN_UNARMED = ("Dörren är inte aktiverad på den här servern — "
                 "ingen uppgift är lagrad")   # 503, fail-closed. MC 12602
# F-P3-6: the DISARMED answer is GENERIC — a 503 on the un-armed door must
# not name the door (no ai-rek bytes in an anonymous answer, the no-leak
# posture); which door is disarmed is server config, and a 503 body that
# spells it out hands an unauthenticated prober the route inventory.
TOKEN_REFUSED = ("Dörrnyckeln saknas eller är fel — ingen rekommendation är "
                 "lagrad")           # 401, ONE uniform copy (no oracle)
LENGTH_REQUIRED = (
    "Innehållets längd (Content-Length) saknas — dörren vägrar gissa sig "
    "till vad transporten skickade: skicka listan igen med längden i höljet."
    " Ingen rekommendation är lagrad")   # the /pris F-E2 posture, same rule
ROWS_TOO_BIG = ("AI-listan är {antal} rader — budgetet är {max} rader per "
                "anrop; dela upp den. Ingen rekommendation är lagrad")
EMPTY_GENERATION = ("Generationen är tom — ett fullständigt byte måste "
                    "innehålla minst en rad; dörren vägrar radera "
                    "befintliga 'new'-rader utifrån noll rader. Ingen "
                    "rekommendation är lagrad och inga befintliga rader "
                    "har rörts")            # MC 12616, fail-loud: mass-delete
# by an empty payload is the footgun the card names — refused BEFORE the DB.
NOT_A_LIST = ("AI-listan är inte en JSON-array av objekt — dörren tar emot "
              "[{title, author_name, isbn13, year, reason, source, fit,"
              " kategori}, …]. Ingen rekommendation är lagrad")

KATEGORIER = ("nyhet", "klassiker", "blandad")   # the table's CHECK vocabulary

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
    kategori = row.get("kategori")
    if kategori is not None and kategori not in KATEGORIER:
        # the table's CHECK, asked AT the door (the /pris posture: the
        # named evaluator answers, the CHECK never fires mid-commit).
        return "shape", None
    return None, {"rec_key": isbn if isbn is not None
                  else seed.book_key(title, [author or ""]),
                  "boknyckel": onska.wish_key(title, author or ""),
                  "isbn13": isbn, "title": title, "author_name": author,
                  "year": year, "reason": reason, "source": source,
                  "fit": float(fit), "kategori": kategori}


def _samma_bock(identitet, obs):
    """MC 12616 — the fix-wave matcher's identity UNION extracted verbatim
    as a predicate (MC 12602 F-P1-1): the UNIQUE `rec_key` lane, the isbn
    lane when BOTH sides carry one, and the §5.3 normalized title+author
    lane through `onska.wish_key`. ONE mechanism, two callers: `_bok_rad`
    uses it to FIND the row of a book, `_sweepa` uses it INVERTED to find
    the `new` rows absent from a complete generation. No second "same book"
    rule may ever be written beside it."""
    rec_key, isbn, titel, forfattare = identitet
    return (rec_key == obs["rec_key"]
            or (obs["isbn13"] is not None and isbn == obs["isbn13"])
            or onska.wish_key(titel, forfattare or "") == obs["boknyckel"])


def _bok_rad(conn, obs):
    """The row that already carries THIS BOOK, or None — MC 12602 F-P1-1's
    whole-identity match: the UNIQUE `rec_key` lane, the isbn lane (when
    BOTH sides carry one), and the normalized title+author lane through
    `onska.wish_key` — THE app's §5.3 identity normalization (seed.book_key
    NFD+casefold+strip, authors sorted; alias canonicalization via
    app_aliases, the same chain the wish rows are keyed by — the door's
    "same book" IS the wish's "same book", never a second one). A DECIDED
    row wins the match wherever it stands in the table: one book, one card,
    and the decision holds on EITHER identity — re-spelling the title,
    aliasing the author or moving the isbn in/out cannot mint a second card
    to decline again, nor walk a decision back. Later `new` matches are
    returned as `duppar`: the pre-fix identity split, merged (deleted) by
    the caller BEFORE the refresh lands the shared rec_key on the target —
    only `new` rows can ever be merged, the guarded DELETE says so. The
    lane predicate itself lives in `_samma_bock` — ONE mechanism shared
    with `_sweepa`, never a second copy."""
    ny = None
    duppar = []
    for id_, state, rkey, isbn, titel, forf in conn.execute(
            "SELECT id, state, rec_key, isbn13, title, author_name"
            " FROM ai_rek ORDER BY id"):
        if not _samma_bock((rkey, isbn, titel, forf), obs):
            continue
        if state in ("accept", "decline"):
            return state, id_, ()
        if ny is None:
            ny = id_
        else:
            duppar.append(id_)
    if ny is None:
        return None
    return "new", ny, duppar


def _uppdatera(conn, obs, nu, rad_id):
    """The refresh of one matched row — rec_key included, so the row also
    follows the book's newest identity; guarded to state 'new' (a decided
    row is UNTOUCHABLE, also mid-transaction)."""
    conn.execute(
        "UPDATE ai_rek SET rec_key = ?, title = ?, author_name = ?,"
        " isbn13 = ?, year = ?, reason = ?, source = ?, fit = ?,"
        " kategori = ?, ts = ? WHERE id = ? AND state = 'new'",
        (obs["rec_key"], obs["title"], obs["author_name"], obs["isbn13"],
         obs["year"], obs["reason"], obs["source"], obs["fit"],
         obs["kategori"], nu, rad_id))


def _sweepa(conn, payload):
    """MC 12616 (PLAN §d completion) — the full-swap sweep: DELETE the
    state='new' rows whose identity is ABSENT from the COMPLETE new
    generation. Identity is THE SAME union the fix-wave matcher `_bok_rad`
    matches on, asked INVERTED through `_samma_bock` — one mechanism, two
    callers. accept/decline rows are NEVER deleted: the DELETE rides the
    same `AND state = 'new'` guard as the duppar merge (decline permanence
    holds on every identity, absent or variant). The empty payload is the
    door's own 400 refusal (`EMPTY_GENERATION` — mass-delete by zero rows
    is the footgun the card names); the belt stands HERE too: zero VALID
    identities sweep NOTHING, so 500 shape-garbage rows cannot retire a
    single live row either."""
    if not payload:
        return 0
    bort = 0
    for id_, rec_key, isbn, titel, forfattare in conn.execute(
            "SELECT id, rec_key, isbn13, title, author_name FROM ai_rek"
            " WHERE state = 'new' ORDER BY id"):
        if not any(_samma_bock((rec_key, isbn, titel, forfattare), obs)
                   for obs in payload):
            bort += conn.execute("DELETE FROM ai_rek WHERE id = ?"
                                 " AND state = 'new'", (id_,)).rowcount
    return bort


def ingest(conn, rows, *, generation=False):
    """One POST's rows through shape + whole-identity upsert; returns the
    aggregate counters and ZERO book data (the echo rule, pris.py's
    response). The upsert asks for the book BEFORE the write (the pris
    `_store` posture): a decided row is counted kept and left UNTOUCHED —
    the one rule that makes "declines never resurface" the door's promise,
    not the page's, and F-P1-1's fix makes it hold on every identity the
    book can arrive under. The INSERT rides `ON CONFLICT(rec_key) DO
    NOTHING` (MC 12602 F-P3-7, the /pris race posture): a concurrent POST
    that won the UNIQUE lane is RE-ASKED, never an IntegrityError and
    never a whole lost generation. `generation=True` (MC 12616, the
    envelope the door unwraps) makes the SAME upsert a FULL SWAP: after
    every row is settled, `_sweepa` deletes the `new` rows whose identity
    is absent from this complete generation and the answer gains
    `deleted_n`; mode OFF the answer is byte-identical to today."""
    counts = {k: 0 for k in ("accepted", "inserted", "updated",
                             "kept_accept", "kept_decline",
                             "rejected_shape")}
    nu = auth.utcnow_iso()               # SERVER clock only, one read/POST
    payload = []                         # the generation's VALID identities
    for row in rows:
        reject, obs = _obs(row)
        if reject:
            counts["rejected_shape"] += 1
            continue
        payload.append(obs)
        match = _bok_rad(conn, obs)
        if match is not None:
            state, rad_id, duppar = match
            if state in ("accept", "decline"):
                counts[f"kept_{state}"] += 1
                continue
            for dup in duppar:
                conn.execute("DELETE FROM ai_rek WHERE id = ?"
                             " AND state = 'new'", (dup,))
            _uppdatera(conn, obs, nu, rad_id)
            counts["updated"] += 1
        else:
            cur = conn.execute(
                "INSERT INTO ai_rek (rec_key, isbn13, title, author_name,"
                " year, reason, source, fit, kategori, ts)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(rec_key) DO NOTHING",
                (obs["rec_key"], obs["isbn13"], obs["title"],
                 obs["author_name"], obs["year"], obs["reason"],
                 obs["source"], obs["fit"], obs["kategori"], nu))
            if cur.rowcount == 0:
                dot = conn.execute("SELECT id, state FROM ai_rek"
                                   " WHERE rec_key = ?",
                                   (obs["rec_key"],)).fetchone()
                if dot[1] in ("accept", "decline"):
                    counts[f"kept_{dot[1]}"] += 1
                else:
                    _uppdatera(conn, obs, nu, dot[0])
                    counts["updated"] += 1
            else:
                counts["inserted"] += 1
        counts["accepted"] += 1
    if generation:
        counts["deleted_n"] = _sweepa(conn, payload)   # same transaction
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


def läs_nycklar(conn):
    """MC 12643 (M11-N9a, the owner's ruling "A") — the COMPLETE read-title
    list the door's GET answers: EVERY `bok` row, ALL statuses (read AND
    wishlist — the runner excludes both, she is never offered a book she
    owns), as {titel, forfattare, status} objects ONLY. The runner needs
    the §5.3 identity fields and nothing else, so the body carries ZERO
    secret bytes: no isbn, no dates, no `book_key`, no notes, no rating.
    Authors are the book's OWN names joined with ", " — the delimiter
    `seed.split_authors` splits on — so the runner re-keys the list
    through THE SAME `onska.wish_key` chain `_samma_bock`'s identity law
    uses (alias table authors-only, the ONE spelling mechanism, never a
    second)."""
    rader = []
    for titel, status, författare in conn.execute(
            "SELECT b.title, b.status,"
            " (SELECT group_concat(a.name, ', ') FROM author a"
            "   JOIN book_author ba ON ba.author_id = a.id"
            "  WHERE ba.book_id = b.id ORDER BY a.name)"
            " FROM book b ORDER BY b.id"):
        rader.append({"titel": titel, "forfattare": författare,
                      "status": status})
    return rader


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
        the guard's uniform 302 (auth._is_ai_rek_door is POST-only).
        MC 12616: a JSON OBJECT carrying the key "generation" is the
        full-swap envelope — its row list is unwrapped and must be a
        non-empty array (an empty one is the named 400 `EMPTY_GENERATION`
        BEFORE any row is read), and the ingest that follows is a COMPLETE
        generation whose absent `new` rows are swept (deleted_n in the
        answer). Every other payload keeps today's upsert path byte-for-
        byte, envelope checks included."""
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
        generation = isinstance(rows, dict) and "generation" in rows
        if generation:                       # MC 12616 full-swap envelope
            rows = rows["generation"]
            if not isinstance(rows, list):
                return NOT_A_LIST, 400
            if not rows:                     # the footgun, refused BEFORE
                return EMPTY_GENERATION, 400  # a single row is read
        if not isinstance(rows, list):
            return NOT_A_LIST, 400
        if len(rows) > MAX_AI_REK_ROWS:
            return ROWS_TOO_BIG.format(antal=len(rows),
                                        max=MAX_AI_REK_ROWS), 400
        return jsonify(ingest(db.get_db(), rows, generation=generation))

    @app.get("/ai-rek/library-keys")
    def ai_rek_library_keys():
        """MC 12643 (M11-N9a) — the read-title door, THE SAME credential
        posture as the POST, `_door_refused` FIRST and verbatim: disarmed
        env ⇒ the GENERIC 503 (zero ai-rek bytes, MC 12602 F-P3-6 — a GET
        is an anonymous-reachable answer the moment its header rides),
        present-but-empty-or-wrong token ⇒ the ONE uniform 401 copy (no
        oracle), a valid owner session rides WITHOUT the header exactly as
        on the POST. An anonymous request WITHOUT the header never gets
        here at all: auth._is_ai_rek_keys lets the GET through only when
        the credential rides, so the no-header face is the guard's uniform
        302 — byte-for-byte what an anonymous GET /ai-rek answers TODAY
        (that route's POST-only door allow is untouched). 200 ⇒
        `läs_nycklar`: every bok row as {titel, forfattare, status}, zero
        secret bytes, ZERO writes (a read door)."""
        refused = _door_refused()
        if refused is not None:
            return refused
        return jsonify(läs_nycklar(db.get_db()))

    @app.post("/ai-rek/<int:rek_id>/accept")
    def ai_rek_accept(rek_id):
        """Owner POST: guard + CSRF already ran (session-guarded, token
        required — the /djem pattern, NOT a TOKENLESS machine route).
        Unknown id ⇒ plain 404, echo nothing (the /djem idiom). MC 12602
        F-P2-3 reorders the write: THE WISH WRITER RUNS FIRST and the
        state flip lands only AFTER it succeeded, each in its own committed
        transaction — a raising writer leaves state 'new' with a named 400
        and the retry works (the first shipped order committed an
        accept-no-wish and made the retry answer "already decided", i.e.
        the failed accept was unrecoverable). "redan" (already wished)
        still counts as the accept succeeding. A row already decided
        ('accept' or 'decline') is a no-op redirect: the second accept
        writes no second wish, the declined stay down — and the flip's own
        `state='new'` guard keeps a concurrent double-click from ever
        un-deciding."""
        conn = db.get_db()
        rad = conn.execute("SELECT title, author_name, isbn13, year, state"
                           " FROM ai_rek WHERE id = ?", (rek_id,)).fetchone()
        if rad is None:
            abort(404)                       # the 404 page echoes nothing
        if rad[4] != "new":
            return auth.redirect_prefixed("/rekommendationer")
        try:
            # THE wish writer (isbn/year validated inside it, F-P2-2).
            onska.skapa_onska(conn, rad[0], rad[1] or "",
                              isbn13=rad[2], year=rad[3])
        except Exception:
            conn.rollback()                  # the writer's own rollback, and
            return render_template(          # the flip never ran: state new
                "csrf-fel.html",
                fel="Boken kunde inte läggas på önskelistan — "
                    "försök igen."), 400
        conn.execute("UPDATE ai_rek SET state = 'accept', ts = ?"
                     " WHERE id = ? AND state = 'new'",
                     (auth.utcnow_iso(), rek_id))
        conn.commit()
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
