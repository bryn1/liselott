"""T5.4 — the wishlist and the §5.11 transition contract.

§5.11 (binding) read in full: transitions happen ONLY through app routes, and
read→wishlist NEVER happens. So this module has exactly two write doors:
lagg-till (a wish is BORN as a wish — status 'wishlist', the read_year 0
sentinel, no date) and /las (the ONE flip to read with a date; grading is the
other flip, in routes.py, and it names no date). Both go through the shared
write primitives in app/seed.py; the delete door is T5.2's /ta-bort/<id> —
one delete, not two.
"""
from datetime import date

from flask import abort, render_template, request

from app import auth, books, db, priskort, redigera, search, seed


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
        # NULL, never the machine's un-validated token into book identity
        # (the /pris price resolve joins on book.isbn13).
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


def init_onska(app):

    def _onska(vyan, fel):
        """ONE render of the page for its three states (the list, a validation
        error, a duplicate). `prisar` rides with all three (M9a-1, DESIGN §5):
        the owner's rows carry the SAME price line /bibliotek's wishlist
        section does, from the same one read — a fourth render that forgot it
        is exactly the second mechanism this file exists to avoid."""
        return render_template("onska.html", onska=vyan, fel=fel,
                               prisar=priskort.card_prices(db.get_db(), vyan),
                               current="onska")

    @app.get("/onska")
    def onska():
        conn = db.get_db()
        wishes = books.sort_by_read_date(
            [b for b in books.load_books(conn) if b["status"] != "read"])
        return _onska(wishes, None)

    @app.post("/onska/lagg-till")
    def onska_lagg_till():
        conn = db.get_db()
        form = dict(request.form)
        form.setdefault("titel", "")
        values, fel = redigera.form_to_fields(form, {})   # THE shared validator
        if fel:
            wishes = books.sort_by_read_date(
                [b for b in books.load_books(conn) if b["status"] != "read"])
            return _onska(wishes, fel), 400
        # MC 12597: the write itself moved ONE step into skapa_onska (the
        # accept route is its second caller); the POST contract here is
        # byte-identical — the writer gets no isbn/year, as before.
        if skapa_onska(conn, values["title"], form.get("forfattare", ""),
                       format=form.get("format")) == "redan":
            wishes = books.sort_by_read_date(
                [b for b in books.load_books(conn) if b["status"] != "read"])
            return _onska(
                wishes, "Den boken står redan på önskelistan."), 400
        return auth.redirect_prefixed("/onska")

    @app.post("/onska/<int:id>/las")
    def onska_las(id):
        """The ONE door that turns a wish into a read WITH a date (§5.11).
        mark_read owns the flip + the read_year sentinel; the date is named
        HERE because naming a date is what this door means."""
        conn = db.get_db()
        row = conn.execute("SELECT status FROM book WHERE id = ?",
                           (id,)).fetchone()
        if row is None:
            abort(404)
        if row[0] != "wishlist":
            return render_template(
                "csrf-fel.html",
                fel="Den boken är redan läst — läsdatumet ändras här."), 400
        seed.mark_read(conn, id)
        conn.execute("UPDATE book SET date_read = ?, updated = ? WHERE id = ?",
                     (date.today().isoformat(), auth.utcnow_iso(), id))
        conn.commit()
        return auth.redirect_prefixed(f"/bok/{id}")
