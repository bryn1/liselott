"""T5.4 — the wishlist and the §5.11 transition contract.

§5.11 (binding) read in full: transitions happen ONLY through app routes, and
read→wishlist NEVER happens. MC 12733 (M12 W1) grew the module's write doors
from two to FOUR (R6): lagg-till (a wish is BORN as a wish — status
'wishlist', the read_year 0 sentinel, no date), las-nu (a book ENTERS "Läser
nu" from 'wishlist' or 'aborted' — a resume; no date, no year), avbryt (the
ONLY 'reading'→'aborted' flip), and /las (the dated door: wishlist|reading →
read — `read → read` never happens). Grading (routes.py, /betyg) is the
other flip-to-read and names no date; BOTH flips-to-read go through the
shared write primitive in app/seed.py (mark_read), las-nu/avbryt write the
status token HERE (mark_read's law is the flip to READ — §5.11's one flip
it owns, F-B/R4), and the delete door is T5.2's /ta-bort/<id> — one delete,
not two. The wish rows the /onska page lists follow the ONE wish law
`status == 'wishlist'` (F-A), at every render state, from ONE read.
MC 12735 (M12 W3) added this module's READ face too: GET /slump (PLAN-M12
§4, R3) — the quiet draw whose pool IS the wish rows, the same law at the
same ONE place: one module for the wishlist's UI.
"""
from datetime import date
import random

from flask import abort, render_template, request

from app import auth, books, db, redigera, search, seed


def wish_key(titel, forfattare):
    """§5.3's key for ONE book's identity: the one chain the wish rows are
    keyed by — `split_authors` + `app_aliases` canonicalization feeding
    `seed.book_key` (NFD + casefold + strip, authors sorted AFTER
    normalization, seed.py §5.3 — THE app's named book-identity
    normalization). MC 12602 F-P1-1: the ai_rek door matches incoming
    rows through THIS function too, so the door's "same book" and the
    wish's "same book" (alias spellings included, since the alias table
    is the app's only spelling mechanism) can never mean different
    things — one identity implementation, two callers."""
    aliases = seed.app_aliases()
    return seed.book_key(titel, [aliases.get(name, name)
                                 for name in seed.split_authors(forfattare)])


def skapa_onska(conn, titel, forfattare, isbn13=None, year=None,
                format="bok"):
    """M11 (MC 12597) — THE one wish writer: the INSERT body of
    /onska/lagg-till extracted one step, so the accept route and the form
    route cannot drift (one writer, two callers; §5.4's anti-drift rule
    speaks of splitters but binds for writers too). `forfattare` is the raw
    display string — the author split and the §5.3 key run through the
    SAME chain (`wish_key`), so the stored author rows and the book_key
    cannot disagree, exactly as inside the route before the move. Returns
    None on success and the sentinel "redan" on the UNIQUE book_key
    collision (§5.3) — the CALLER owns the Swedish copy, because one caller
    re-renders a form and the other redirects. `isbn13`/`year` ride for the
    accept path (an AI rec carries them; the form route has never stored
    them — enrichment owns that door, /backfill). The §5.11 posture is
    untouched: a wish is BORN as a wish — status 'wishlist', the read_year
    0 sentinel, no date."""
    authors = seed.split_authors(forfattare)
    if isbn13 is not None:
        # MC 12602 F-P2-2 (PLAN §d was right): the ISBN runs through THE §7
        # mechanism, search.normalize_isbn — the same canonical validation
        # /lagg-till performs via form_to_fields, now living with the writer
        # so the machine caller cannot skip what the form caller pays. A
        # check-digit failure is NO isbn, not a string: the wish row gets
        # NULL, never the machine's un-validated token into book identity.
        got = search.normalize_isbn(isbn13)
        isbn13 = got[0] if got else None
    nu = auth.utcnow_iso()
    try:
        cur = conn.execute(
            "INSERT INTO book (title, format, read_year, status, isbn13,"
            " year, book_key, created, updated) VALUES (?,?,0,'wishlist',?"
            ",?,?,?,?)",
            (titel, format if format in redigera.FORMATS else "bok",
             isbn13, year, wish_key(titel, forfattare), nu, nu))
        seed.set_authors(conn, cur.lastrowid, authors)
        conn.commit()
    except Exception as e:
        conn.rollback()
        if "UNIQUE" not in str(e):
            raise
        return "redan"
    return None


def onskelistan(conn):
    """THE /onska page's rows, on the ONE wish law `status == 'wishlist'`
    (F-A — never the wide `!= 'read'`, which after the widened domain would
    list a "läser nu" or "Avbruten" book on "Att läsa" beside its old
    button). ONE read for the page's three render states — the same
    anti-drift reason as `_onska`'s ONE render and `skapa_onska`'s ONE
    writer (§5.4's rule, spoken for writers, honoured for readers)."""
    return books.sort_by_read_date(
        [b for b in books.load_books(conn) if b["status"] == "wishlist"])


def slump_pool(conn):
    """THE draw's pool (MC 12735, PLAN-M12 §4): the SAME wish rows the page
    lists — `status == 'wishlist'` through the ONE loader — in the loader's
    OWN id order (a draw must be reproducible, and reproducibility starts
    with a deterministic pool; the page's display sort would reorder rows and
    a seed would mean nothing). F-A's law makes the page's list, the head
    link's count and this pool ONE set by predicate: the failure the old wide
    wording hid — a wide list, a narrow pool, "count > 0" yet the draw
    answers "Önskelistan är tom." — cannot exist under one `== 'wishlist'`."""
    return [b for b in books.load_books(conn) if b["status"] == "wishlist"]


def init_onska(app):

    def _onska(vyan, fel):
        """ONE render of the page for its three states (the list, a validation
        error, a duplicate) — the reason MC 12542's price map once cost this
        file nothing to add (and why MC 12606's retirement costs it nothing
        to remove): a fourth hand-written render is the second mechanism this
        file exists to avoid."""
        return render_template("onska.html", onska=vyan, fel=fel,
                               current="onska")

    @app.get("/onska")
    def onska():
        conn = db.get_db()
        return _onska(onskelistan(conn), None)

    @app.get("/slump")
    def slump():
        """MC 12735 (M12 W3, PLAN-M12 §4): the quiet draw. ONE calm bokkort
        out of the wishlist, a quiet "Smaka på en annan" redraw link, the way
        back to /onska. Owner-only BY GUARD (the path rides no PUBLIC_READ
        list — the guard's uniform 302 answers an anonymous GET). The draw
        goes through the MODULE NAME `random` so a test can hand the route a
        seeded chooser (the house seam — determinism as a TEST property: the
        row is never marked, consumed or remembered by being drawn; §4's
        "no bookkeeping" keeps the page honest). An empty pool is the
        template's ONE quiet line, never a dead card."""
        pool = slump_pool(db.get_db())
        return render_template("slump.html", current="onska",
                               bok=random.choice(pool) if pool else None)

    # The explicit slash rule beside the canonical one (aret.py's W2
    # precedent on the ai_rek.py F-3 line): registered AFTER the view, so the
    # first rule of the endpoint — the one url_for builds — stays the
    # canonical "/slump". The anonymous /slump/ meets the guard's uniform 302
    # before the router, slash-stripped or not.
    app.add_url_rule("/slump/", endpoint="slump")

    @app.post("/onska/lagg-till")
    def onska_lagg_till():
        conn = db.get_db()
        form = dict(request.form)
        form.setdefault("titel", "")
        values, fel = redigera.form_to_fields(form, {})   # THE shared validator
        if fel:
            return _onska(onskelistan(conn), fel), 400
        # MC 12597: the write itself moved ONE step into skapa_onska (the
        # accept route is its second caller); the POST contract here is
        # byte-identical — the writer gets no isbn/year, as before.
        if skapa_onska(conn, values["title"], form.get("forfattare", ""),
                       format=form.get("format")) == "redan":
            return _onska(
                onskelistan(conn), "Den boken står redan på önskelistan."), 400
        return auth.redirect_prefixed("/onska")

    @app.post("/onska/<int:id>/las-nu")
    def onska_las_nu(id):
        """MC 12733 (R6): a book ENTERS "Läser nu" from 'wishlist' or
        'aborted' (a resume) and from nowhere else — a `read` row meets the
        door (§5.11: `read → anything` never happens here). The flip is the
        WHOLE transition: no date, no year (naming a date is /las's meaning,
        the year is mark_read's), so the wish's 0 sentinel keeps its law."""
        conn = db.get_db()
        row = conn.execute("SELECT status FROM book WHERE id = ?",
                           (id,)).fetchone()
        if row is None:
            abort(404)
        if row[0] not in ("wishlist", "aborted"):
            return render_template(
                "csrf-fel.html",
                fel="Endast en önskan eller en avbruten bok kan läsas nu."), 400
        conn.execute("UPDATE book SET status = 'reading', updated = ?"
                     " WHERE id = ?", (auth.utcnow_iso(), id))
        conn.commit()
        return auth.redirect_prefixed(f"/bok/{id}")

    @app.post("/onska/<int:id>/avbryt")
    def onska_avbryt(id):
        """MC 12733 (R6): the ONLY 'reading'→'aborted' door. The row keeps
        the read_year 0 sentinel and no date — mark_read never ran on it —
        which is what lands an avbruten row under "Utan år" in any public
        grouping BY LAW (the F-E ruling leans on exactly this)."""
        conn = db.get_db()
        row = conn.execute("SELECT status FROM book WHERE id = ?",
                           (id,)).fetchone()
        if row is None:
            abort(404)
        if row[0] != "reading":
            return render_template(
                "csrf-fel.html",
                fel="Endast en bok du läser nu kan avbrytas."), 400
        conn.execute("UPDATE book SET status = 'aborted', updated = ?"
                     " WHERE id = ?", (auth.utcnow_iso(), id))
        conn.commit()
        return auth.redirect_prefixed(f"/bok/{id}")

    @app.post("/onska/<int:id>/las")
    def onska_las(id):
        """The ONE dated door into read (§5.11): since MC 12733 (R6) it
        admits 'wishlist' AND 'reading' — `reading → read` reuses THIS door,
        it is not a second one — and still refuses a read row (`read → read`
        never happens) and an aborted one (resume through las-nu first).
        mark_read owns the flip + the read_year sentinel; the date is named
        HERE because naming a date is what this door means."""
        conn = db.get_db()
        row = conn.execute("SELECT status FROM book WHERE id = ?",
                           (id,)).fetchone()
        if row is None:
            abort(404)
        if row[0] not in ("wishlist", "reading"):
            return render_template(
                "csrf-fel.html",
                fel="Endast en önskan eller en bok du läser nu kan markeras"
                    " läst här."), 400
        seed.mark_read(conn, id)
        conn.execute("UPDATE book SET date_read = ?, updated = ? WHERE id = ?",
                     (date.today().isoformat(), auth.utcnow_iso(), id))
        conn.commit()
        return auth.redirect_prefixed(f"/bok/{id}")
