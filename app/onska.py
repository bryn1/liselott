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

from app import auth, books, db, redigera, seed


def init_onska(app):

    @app.get("/onska")
    def onska():
        conn = db.get_db()
        wishes = books.sort_by_read_date(
            [b for b in books.load_books(conn) if b["status"] != "read"])
        return render_template("onska.html", onska=wishes, fel=None,
                               current="onska")

    @app.post("/onska/lagg-till")
    def onska_lagg_till():
        conn = db.get_db()
        form = dict(request.form)
        form.setdefault("titel", "")
        values, fel = redigera.form_to_fields(form, {})   # THE shared validator
        if fel:
            wishes = books.sort_by_read_date(
                [b for b in books.load_books(conn) if b["status"] != "read"])
            return render_template("onska.html", onska=wishes, fel=fel,
                                   current="onska"), 400
        authors = seed.split_authors(form.get("forfattare", ""))
        aliases = seed.app_aliases()
        canonical = [aliases.get(name, name) for name in authors]
        now = auth.utcnow_iso()
        try:
            cur = conn.execute(
                "INSERT INTO book (title, format, read_year, status,"
                " book_key, created, updated) VALUES (?,?,0,'wishlist',?,?,?)",
                (values["title"], form.get("format") if form.get("format")
                 in ("bok", "ljudbok") else "bok",
                 seed.book_key(values["title"], canonical), now, now))
            seed.set_authors(conn, cur.lastrowid, authors)
            conn.commit()
        except Exception as e:
            conn.rollback()
            if "UNIQUE" not in str(e):
                raise
            wishes = books.sort_by_read_date(
                [b for b in books.load_books(conn) if b["status"] != "read"])
            return render_template(
                "onska.html", onska=wishes,
                fel="Den boken står redan på önskelistan.",
                current="onska"), 400
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
